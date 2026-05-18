from decimal import Decimal

from django.db.models import Sum
from django.db.utils import IntegrityError
from django.test import TestCase

from .models import (AcademicYear, Account, FeeItem, FeeSchedule, Grade,
                     JournalEntry, JournalLine, Payment, Student,
                     StudentTermCharge, Term)
from .services import (apply_discount, charge_student, get_balance,
                       get_charge_type, get_student_ledger,
                       get_student_summary, lock_term, record_payment)


class TermTestCase(TestCase):

    def setUp(self):
        academic_year = AcademicYear.objects.create(
            label="2025-2026",
        )

        self.term = Term.objects.create(
            academic_year=academic_year,
            name="test_term",
            start_date="2025-11-23",
            end_date="2025-12-12",
        )

    def test_locking(self):
        term = lock_term(self.term)

        self.assertEqual(term.status, "locked")
        self.assertIsNotNone(term.locked_at)



class ChargeStudentTestCase(TestCase):
    def setUp(self):
        self.academic_year = AcademicYear.objects.create(
            label="2025-2026",
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="test_term",
            start_date="2025-11-23",
            end_date="2025-12-12",
        )
        self.grade = Grade.objects.create(
            name="Test grade"
        )
        self.student = Student.objects.create(
            name="Test Student",
            grade=self.grade
        )

        test_fee_item = FeeItem.objects.create(name="test")

        fee_schedule = FeeSchedule.objects.create(
            grade=self.grade,
            fee_item=test_fee_item,
            term=self.term,
            amount=300.00,
        )

        # The five accounts
        # 1. Cash/bank: Asset - nomral side DR
        # 2. Accounts Receivable: Asset - normal side - DR
        # 3. Student Deposits: Liability - normal side - CR
        # 4. Fee Income: Revenue - normal side CR
        # 5. Discounts: contra-revenue - normal side DR


    #def test_charges_correct_amount(self):
    #    # Another fee item, just to add ontop of what we have in the setUp method
    #    fee_item = FeeItem.objects.create(name="tuition")
    #    fee_schedule = FeeSchedule.objects.create(
    #        grade=self.grade,
    #        fee_item=fee_item,
    #        term=self.term,
    #        amount=5000.00,
    #    )

    #    # Now I need that balance function

    #    charge_student(self.student, self.term)
    #    pass

    def test_locked_term_raises(self):
        locked_term = Term.objects.create(
            academic_year = self.academic_year,
            name="Locked term",
            start_date="2025-11-23",
            end_date="2025-12-12",
            status="locked"
        )

        with self.assertRaises(Exception, msg="Term locked; does not allow charging"):
            charge_student(self.student, locked_term)

    def test_student_already_charged_raises(self):
        # Charge this student
        # Create a journal entry
        # I don't think I'll need the journal lines here

        journal_entry = JournalEntry.objects.create(
            description="Test charge",
            reference="WHSKDJF",
            term=self.term
        )

        student_term_charge = StudentTermCharge.objects.create(
            student=self.student,
            term=self.term,
            journal_entry=journal_entry,
            amount=300
        )

        with self.assertRaises(Exception, msg="Student already charged for this term"):
            charge_student(self.student, self.term)

    def test_charge_creates_one_journal_entry(self):
        charge_student(self.student, self.term)
        self.assertEqual(JournalEntry.objects.count(), 1)

    def test_charge_creates_two_journal_lines(self):

        journal_entry = charge_student(self.student, self.term)

        journal_lines_count = journal_entry.lines.count()

        self.assertEqual(journal_lines_count, 2)

    def test_raises_if_accounts_missing(self):
        pass


class BalanceTestCase(TestCase):
    def setUp(self):
        self.academic_year = AcademicYear.objects.create(
            label="2025-2026",
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="test_term",
            start_date="2025-11-23",
            end_date="2025-12-12",
        )
        self.grade = Grade.objects.create(
            name="Test grade"
        )
        self.student = Student.objects.create(
            name="Test Student",
            grade=self.grade
        )

        test_fee_item = FeeItem.objects.create(name="test")

        fee_schedule = FeeSchedule.objects.create(
            grade=self.grade,
            fee_item=test_fee_item,
            term=self.term,
            amount=300.00,
        )

        charge_student(self.student, self.term)

    def test_balance_correct(self):
        self.assertEqual(get_balance(self.student), 300)

    def test_negative_balance_with_overpayment(self):

        self.payment = record_payment(
            student=self.student,
            amount=500,
            reference="KJKSJDJFKDFJKJDF",
            payment_method="cash",
            paid_on="2025-04-03"
        )
        self.assertEqual(get_balance(self.student), Decimal("-200.00"))

class PaymentTestCase(TestCase):
    def setUp(self):
        self.academic_year = AcademicYear.objects.create(
            label="2025-2026",
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="test_term",
            start_date="2025-11-23",
            end_date="2025-12-12",
        )
        self.grade = Grade.objects.create(
            name="Test grade"
        )
        self.student = Student.objects.create(
            name="Test Student",
            grade=self.grade
        )

        test_fee_item = FeeItem.objects.create(name="test")

        fee_schedule = FeeSchedule.objects.create(
            grade=self.grade,
            fee_item=test_fee_item,
            term=self.term,
            amount=300.00,
        )

        charge_student(self.student, self.term)

    def test_payment_creates_payment_instance(self):
        payment = record_payment(
            student=self.student,
            amount=150,
            reference="KJKSJDJFKDFJKJDF",
            payment_method="cash",
            paid_on="2025-04-03"
        )

        self.assertEqual(Payment.objects.count(), 1)

    def test_payment_creates_journal_entry(self):
        payment = record_payment(
            student=self.student,
            amount=150,
            reference="KJKSJDJFKDFJKJDF",
            payment_method="cash",
            paid_on="2025-04-03"
        )
        
        self.assertEqual(JournalEntry.objects.count(), 2)

    def test_payment_debits_cash_bank(self):
        # 2 JournalEntries 1 for when charging and one for payment
        payment = record_payment(
            student=self.student,
            amount=150,
            reference="KJKSJDJFKDFJKJDF",
            payment_method="cash",
            paid_on="2025-04-03"
        )
        journal_entry = payment.journal_entry
        cash_bank_account = Account.objects.get(code="1000")

        cash_bank_journal_line = JournalLine.objects.get(
            journal_entry=journal_entry,
            account=cash_bank_account
        )
        self.assertEqual(cash_bank_journal_line.credit, Decimal("0.00"))
        self.assertEqual(cash_bank_journal_line.debit, Decimal("150.00"))

    def test_payment_credits_accounts_receivable(self):
        payment = record_payment(
            student=self.student,
            amount=150,
            reference="KJKSJDJFKDFJKJDF",
            payment_method="cash",
            paid_on="2025-04-03"
        )
        journal_entry = payment.journal_entry
        accounts_receivable = Account.objects.get(code="1001")

        accounts_receivable_journal_line = JournalLine.objects.get(
            journal_entry=journal_entry,
            account=accounts_receivable
        )
        self.assertEqual(accounts_receivable_journal_line.credit, Decimal("150.00"))
        self.assertEqual(accounts_receivable_journal_line.debit, Decimal("0.00"))

    def test_overpayment_credits_student_deposit_account(self):
        payment = record_payment(
            student=self.student,
            amount=500,
            reference="KJKSJDJFJDF",
            payment_method="cash",
            paid_on="2025-04-03"
        )

        journal_entry = payment.journal_entry
        student_deposit_account = Account.objects.get(code="1002")

        student_deposit_journal_line = JournalLine.objects.get(
            journal_entry=journal_entry,
            account=student_deposit_account,
        )
        self.assertEqual(student_deposit_journal_line.credit, Decimal("200.00"))
        self.assertEqual(student_deposit_journal_line.debit, Decimal("0.00"))

    def test_overpayment_on_already_overpayed_account_correct_balance(self):
        # This overpays the account by 200
        payment = record_payment(
            student=self.student,
            amount=500,
            reference="KJKSJDJFJDF",
            payment_method="cash",
            paid_on="2025-04-03"
        )

        # Then we pay again
        payment = record_payment(
            student=self.student,
            amount=500,
            reference="KJssssJDJFJDF",
            payment_method="cash",
            paid_on="2025-04-03"
        )

        self.assertEqual(get_balance(self.student), Decimal("-700.00"))

    def test_payment_raises_when_negative_or_zero(self):
        with self.assertRaises(Exception, msg="amount cannot be <= 0"):
            record_payment(
                student=self.student,
                amount=-1,
                reference="KJKSJDJFJDF",
                payment_method="cash",
                paid_on="2025-04-03"
            )

    def test_payment_reduces_balance(self):
        initial_balance = get_balance(self.student)
        self.assertEqual(initial_balance, Decimal("300.00"))
        record_payment(
            student=self.student,
            amount=50,
            reference="KJKSJDJF",
            payment_method="cash",
            paid_on="2025-04-03"
        )
        self.assertEqual(get_balance(self.student), Decimal("250.00"))

    def test_payment_with_same_ref_raises(self):
        record_payment(
            student=self.student,
            amount=150,
            reference="KJKSJDJFKDFJKJDF",
            payment_method="cash",
            paid_on="2025-04-03"
        )

        # The db will handle this, because I already have unique, wouldn't hurt to test through
        # Catch that and raise my own
        with self.assertRaises(IntegrityError):
            record_payment(
                student=self.student,
                amount=150,
                reference="KJKSJDJFKDFJKJDF",
                payment_method="cash",
                paid_on="2025-04-03"
            )

    def test_orphaned_journal_entry_deleted_for_same_ref_payment(self):
        # Will be handled with transaction.atomic() but still test this
        record_payment(
            student=self.student,
            amount=150,
            reference="KJKSJDJFKDFJKJDF",
            payment_method="cash",
            paid_on="2025-04-03"
        )
        # 2 because, 1 for when we charge the student
        self.assertEqual(JournalEntry.objects.count(), 2)

        try:
            record_payment(
                student=self.student,
                amount=150,
                reference="KJKSJDJFKDFJKJDF",
                payment_method="cash",
                paid_on="2025-04-03"
            )
        except IntegrityError:
            pass

        self.assertEqual(JournalEntry.objects.count(), 2)

class DiscountTestCase(TestCase):
    def setUp(self):
        self.academic_year = AcademicYear.objects.create(
            label="2025-2026",
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="test_term",
            start_date="2025-11-23",
            end_date="2025-12-12",
        )
        self.grade = Grade.objects.create(
            name="Test grade"
        )
        self.student = Student.objects.create(
            name="Test Student",
            grade=self.grade
        )

        test_fee_item = FeeItem.objects.create(name="test")

        fee_schedule = FeeSchedule.objects.create(
            grade=self.grade,
            fee_item=test_fee_item,
            term=self.term,
            amount=300.00,
        )

        self.journal_entry = charge_student(self.student, self.term)

    def test_raises_if_more_than_balance(self):

        with self.assertRaises(Exception):
            apply_discount(self.student, 500)

    def test_credits_accounts_receivable(self):
        self.assertEqual(JournalLine.objects.filter(
            account__code="1001",
            credit__gt=Decimal("0.00")
        ).count(), 0)

        apply_discount(self.student, 100)

        self.assertEqual(JournalLine.objects.filter(
            account__code="1001",
            credit__gt=Decimal("0.00")
        ).count(), 1)

    def test_credits_account_receivable_correct_amount(self):
        apply_discount(self.student, 100)

        line = JournalLine.objects.get(
            account__code="1001",
            credit__gt=Decimal("0.00")
        )
        self.assertEqual(line.credit, Decimal("100.00"))

    def test_debits_discount_account(self):
        self.assertEqual(JournalLine.objects.filter(
            account__code="1004",
            debit__gt=Decimal("0.00")
        ).count(), 0)

        apply_discount(self.student, 100)

        self.assertEqual(JournalLine.objects.filter(
            account__code="1004",
            debit__gt=Decimal("0.00")
        ).count(), 1)

    def test_debits_discount_account_correct_amount(self):
        apply_discount(self.student, 100)

        line = JournalLine.objects.get(
            account__code="1004",
            debit__gt=Decimal("0.00")
        )

        self.assertEqual(line.debit, 100)

    def test_credits_accounts_receivable_correct_amount(self):
        apply_discount(self.student, 100)

        line = JournalLine.objects.get(
            account__code="1001",
            credit__gt=Decimal("0.00")
        )

        self.assertEqual(line.credit, 100)


    def test_discount_reduces_balance(self):
        self.assertEqual(get_balance(self.student), 300)

        apply_discount(self.student, 100)

        self.assertEqual(get_balance(self.student), 200)

    def test_zero_or_less_discount_raises(self):
        with self.assertRaises(Exception):
            apply_discount(self.student, 0)

        with self.assertRaises(Exception):
            apply_discount(self.student, -1)

    def test_discount_journal_entry_balances(self):
        journal_entry = apply_discount(self.student, 100)

        total_debits = journal_entry.lines.aggregate(
            total=Sum("debit")
        )["total"]

        total_credits = journal_entry.lines.aggregate(
            total=Sum("credit")
        )["total"]

        self.assertEqual(total_debits, total_credits)



class StudentSummaryTestCase(TestCase):
    def setUp(self):
        self.academic_year = AcademicYear.objects.create(
            label="2025-2026",
        )

        self.term = Term.objects.create(
            academic_year=self.academic_year,
            name="test_term",
            start_date="2025-11-23",
            end_date="2025-12-12",
        )
        self.grade = Grade.objects.create(
            name="Test grade"
        )
        self.student = Student.objects.create(
            name="Test Student",
            grade=self.grade
        )

        test_fee_item = FeeItem.objects.create(name="test")

        fee_schedule = FeeSchedule.objects.create(
            grade=self.grade,
            fee_item=test_fee_item,
            term=self.term,
            amount=300.00,
        )

    def test_opening_balance_correct(self):
        pass

    def test_get_charges(self):
        charge_student(student=self.student, term=self.term)

        summary = get_student_summary(self.student)

        charges = summary["charges"]

        self.assertEqual(charges, 300)

    def test_get_payments(self):

        charge_student(student=self.student, term=self.term)

        record_payment(
            student=self.student,
            amount=200,
            reference="KJSKJD",
            payment_method="mpesa",
        )

        record_payment(
            student=self.student,
            amount=50,
            reference="KJS",
            payment_method="mpesa",
        )


        summary = get_student_summary(self.student)

        payments = summary["payments"]

        self.assertEqual(payments, 250)


    def test_get_discounts(self):
        charge_student(student=self.student, term=self.term)

        apply_discount(student=self.student, amount=200)

        summary = get_student_summary(self.student)

        self.assertEqual(summary["discounts"], Decimal('200.00'))

    def test_get_deposits_applied(self):
        pass

    def test_get_closing_balance(self):

        # just the current balance
        charge_student(student=self.student, term=self.term)
        record_payment(
            student=self.student,
            amount=50,
            reference="KJS",
            payment_method="mpesa",
        )

        self.assertEqual(get_balance(self.student), Decimal("250.00"))


class StudentEntriesTestCase(TestCase):

    def setUp(self):
        pass

    # Note sure what to test yet




# Charge types
# If normal_side is debit and we debit then that's a charge but if normal_side is charge and that is that is a discount account(contra revenue) then it is not a charge nor a payment it is discount
# if normal_side credit and we credit thats a 
class ChargeTypeTestCase(TestCase):
    def test_charge(self):
        self.assertEqual(get_charge_type("debit", debit=200), "charge")

    def test_payment_discount(self):
        self.assertEqual(get_charge_type("debit", debit=200), "charge")

    def test_payment_not_discount(self):
        self.assertEqual(get_charge_type("debit", debit=200), "charge")
