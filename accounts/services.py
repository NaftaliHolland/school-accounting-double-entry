from decimal import Decimal

from django.db import transaction
from django.db.models import Sum
from django.db.utils import IntegrityError
from django.utils import timezone

from .models import (Account, FeeSchedule, JournalEntry, JournalLine, Payment,
                     Student, StudentTermCharge, Term)


def lock_term(term: Term) -> Term:
    now = timezone.now()

    term.locked_at = now
    term.status = "locked"

    term.save(update_fields=["locked_at", "status"])

    return term

@transaction.atomic
def charge_student(student: Student, term: Term) -> JournalEntry:
    # Charge student for a term

    if term.status != "open":
        raise Exception("Term locked; does not allow charging")

    if StudentTermCharge.objects.filter(
        student=student,
        term=term,
    ).exists():
        raise Exception("Student already charged for this term")

    # get all payments
    total = FeeSchedule.objects.filter(
        grade=student.grade,
        term=term,
    ).aggregate(total_amount=Sum('amount'))["total_amount"] or 0

    journal_entry = JournalEntry.objects.create(
        description="Test charge",
        term=term
    )

    accounts_receivable = Account.objects.get(code="1001")
    fee_income_account = Account.objects.get(code="1003")

    JournalLine.objects.bulk_create([
        JournalLine(
            journal_entry=journal_entry,
            account=accounts_receivable,
            student=student,
            debit=total,
        ),
        JournalLine(
            journal_entry=journal_entry,
            account=fee_income_account,
            student=student,
            credit=total,
        ),
    ])

    student_term_charge = StudentTermCharge.objects.create(
        student=student,
        term=term,
        journal_entry=journal_entry,
        amount=total,
    )

    return journal_entry

    # Term must be open - raises if not
    # Student should not have been already charged for that term - I don't even know how I'll figure this out
    # Get the students class/grade
    # Early return / or raise exception if the student doens't have a class
    # Get the FeeSchedule for that grade for that particular term
    # Sum all fee items
    # Early return / raises if that grade doesn't have a schedule

    # Post a journal entry
    # - DR Accounts Receivable - JournalLine
    # - CR Fee Income - JournalLine

def get_balance(student):

    student_AR_lines = JournalLine.objects.filter(
        student=student,
        account__code="1001",
    ).select_related('account')

    student_deposit_lines = JournalLine.objects.filter(
        student=student,
        account__code="1002",
    ).select_related('account')

    debits_total_AR = student_AR_lines.aggregate(total=Sum('debit'))['total'] or 0

    credits_total_AR = student_AR_lines.aggregate(total=Sum('credit'))['total'] or 0

    debits_total_student_deposits = student_deposit_lines.aggregate(total=Sum('debit'))['total'] or 0

    credits_total_student_deposits = student_deposit_lines.aggregate(total=Sum('credit'))['total'] or 0

    overpayments = credits_total_student_deposits - debits_total_student_deposits

    balance = debits_total_AR - credits_total_AR

    return -overpayments if overpayments > 0 else balance


@transaction.atomic
def record_payment(
        student: Student,
        amount: int,
        reference: str,
        payment_method: str | None=None,
        paid_on: str | None=None,
) -> Payment:
    if amount <= 0:
        raise Exception("amount cannot be <= 0")

    journal_entry = JournalEntry.objects.create(
        description=f"Payment for {student.name} paid on {paid_on}",
        reference=reference,
    )

    payment = Payment.objects.create(
        amount=amount,
        payment_method=payment_method,
        reference=reference,
        paid_on=paid_on,
        student=student,
        journal_entry=journal_entry
    )

    cash_bank_account = Account.objects.get(code="1000")
    accounts_receivable = Account.objects.get(code="1001")
    student_deposit = Account.objects.get(code="1002")

    journal_lines = [
        JournalLine(
            journal_entry=journal_entry,
            account=cash_bank_account,
            student=student,
            debit=amount,
        ),
    ]

    balance = get_balance(student)

    if balance - amount >= 0:
        journal_lines.append(
            JournalLine(
                journal_entry=journal_entry,
                account=accounts_receivable,
                student=student,
                credit=amount,

            )
        )

    elif balance - amount < 0:
        if balance > 0:
            journal_lines.append(
                JournalLine(
                    journal_entry=journal_entry,
                    account=accounts_receivable,
                    student=student,
                    credit=balance,

                )
            )
            remainder = amount - balance
            if remainder > 0:
                journal_lines.append(
                    JournalLine(
                        journal_entry=journal_entry,
                        account=student_deposit,
                        student=student,
                        credit=remainder,
                    )
                )

        elif balance <= 0:
            journal_lines.append(
                JournalLine(
                    journal_entry=journal_entry,
                    account=student_deposit,
                    student=student,
                    credit=amount,
                )
            )

    JournalLine.objects.bulk_create(journal_lines)

    return payment

@transaction.atomic
def apply_discount(student: Student, amount) -> JournalEntry:
    balance = get_balance(student)

    if amount <= 0:
        raise Exception("Amount cannot be less than or equal to 0")

    if amount > balance:
        raise Exception("Discount cannot be greater than what the student owes")


    journal_entry = JournalEntry.objects.create(
        description=f"Discount applied for {student.name}",
    )

    AR_account = Account.objects.get(code="1001")
    discount_account = Account.objects.get(code="1004")

    journal_lines = [
        JournalLine(
            journal_entry = journal_entry,
            account=AR_account,
            student=student,
            credit=amount
        ),
    JournalLine(
        journal_entry = journal_entry,
        account=discount_account,
        student=student,
        debit=amount
    )
    ]

    JournalLine.objects.bulk_create(journal_lines)

    return journal_entry


def get_student_summary(student: Student) -> dict:

    summary = dict()

    charges_total = JournalLine.objects.filter(
        account__code="1001",
        student=student
    ).aggregate(total=Sum("debit"))["total"]

    summary["charges"] = charges_total

    payments_total = JournalLine.objects.filter(
        account__code="1001",
        student=student
    ).aggregate(total=Sum("credit"))["total"]

    summary["payments"] = payments_total

    discounts_total = JournalLine.objects.filter(
        account__code="1004",
        student=student
    ).aggregate(total=Sum("debit"))["total"]

    summary["discounts"] = discounts_total

#  "summary": {
#    "charges": 45000,
#    "payments": 30000,
#    "discounts": 5000,
#    "deposits_applied": 2000,
#    "closing_balance": 20000
#  },

    return summary

def get_charge_type(normal_side: str, credit=0, debit=0):

    if normal_side == "credit" and credit > 0:
        return "payment"
    elif normal_side == "debit" and debit > 0:
        return "charge"
def get_student_ledger(student: Student):

    ledger = dict()

    ledger["student"] = {
        "id": student.id,
        "name": student.name
    }

    journal_lines = JournalLines.objects.filter(
        student=student,
        account__code__in = ["1001", "1002", "1004"]
    )

    entries = list()

    for journal_line in journal_lines:
        entries.append(
            {
                "id": journal_line.id,
                "date": journal_line.journal_entry.created_at,
            }
        )


#{
#  "student": {
#    "id": "stu_123",
#    "name": "John Doe"
#  },
#
#  "entries": [
#    {
#      "id": "txn_001",
#      "date": "2026-01-10",
#      "type": "charge",
#      "reference": "INV-2026-001",
#      "description": "Term 1 Tuition",
#      "debit": 45000,
#      "credit": 0,
#      "running_balance": 45000,
#      "account": {
#        "code": "1001",
#        "name": "Accounts Receivable"
#      }
#    },
#    {
#      "id": "txn_002",
#      "date": "2026-01-15",
#      "type": "payment",
#      "reference": "RCPT-2026-002",
#      "description": "M-Pesa Payment",
#      "debit": 0,
#      "credit": 30000,
#      "running_balance": 15000,
#      "account": {
#        "code": "1001",
#        "name": "Accounts Receivable"
#      },
#      "payment_method": "mpesa"
#    },
#    {
#      "id": "txn_003",
#      "date": "2026-01-20",
#      "type": "discount",
#      "reference": "DISC-001",
#      "description": "Scholarship",
#      "debit": 0,
#      "credit": 5000,
#      "running_balance": 10000,
#      "account": {
#        "code": "1004",
#        "name": "Discount"
#      }
#    }
#  ]
#}
