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
        reference="WHSKDJF",
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
):
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
        journal_lines.append(
            JournalLine(
                journal_entry=journal_entry,
                account=accounts_receivable,
                student=student,
                credit=balance,

            )
        )
        journal_lines.append(
            JournalLine(
                journal_entry=journal_entry,
                account=student_deposit,
                student=student,
                credit=amount - balance,
            )
        )

    JournalLine.objects.bulk_create(journal_lines)

    return payment
