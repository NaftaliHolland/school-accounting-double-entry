from decimal import Decimal

from django.db import models

# Create your models here.


# Admin models

class AcademicYear(models.Model):
    label = models.CharField(max_length=100)
    is_active = models.BooleanField(default=True)

    def __str__(self):
        return self.label

class Term(models.Model):
    TERM_CHOICES = [
        ("open", "OPEN"),
        ("locked", "LOCKED"),
    ]

    academic_year = models.ForeignKey(AcademicYear, on_delete=models.PROTECT, related_name="terms")
    name = models.CharField(max_length=100)
    start_date = models.DateField()
    end_date = models.DateField()
    status = models.TextField(max_length=20, choices=TERM_CHOICES, default="open")
    locked_at = models.DateTimeField(null=True, blank=True)

    def __str__(self):
        return self.name

    def is_open(self):
        return self.status == "open"

class Grade(models.Model):
    name = models.CharField(max_length=100)

    def __str__(self):
        return self.name

class FeeItem(models.Model):
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True, null=True)

    def __str__(self):
        return self.name

class FeeSchedule(models.Model):
    grade = models.ForeignKey(Grade, on_delete=models.PROTECT, related_name="fee_schedules")
    fee_item = models.ForeignKey(FeeItem, on_delete=models.PROTECT, related_name="fee_schedules")
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name="fee_schedules")
    amount = models.PositiveIntegerField()


    def __str__(self):
        return f"{self.grade} | {self.fee_item} | {self.term} -> {self.amount}"

class Student(models.Model):
    name = models.CharField(max_length=200)
    grade = models.ForeignKey(Grade, on_delete=models.PROTECT, related_name="students")
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

# Accounting models
class Account(models.Model):

    # TODO: Add a description

    ACCOUNT_TYPE_CHOICES = [
        ("asset", "Asset"),
        ("liability", "Liability"),
        ("income", "Income"),
        ("contra_revenue", "Contra-REvenue"),
        ("expense", "Expense")
    ]

    NORMAL_SIDE_CHOICES = [
        ("debit", "Debit"),
        ("credit", "Credit"),
    ]

    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=100)
    type = models.CharField(max_length=20, choices=ACCOUNT_TYPE_CHOICES)
    normal_side = models.CharField(max_length=20, choices=NORMAL_SIDE_CHOICES)


    def __str__(self):
        return self.name


class JournalEntry(models.Model):

    created_at = models.DateTimeField(auto_now_add=True)
    description = models.CharField(max_length=255, blank=True, null=True)
    reference = models.CharField(max_length=100, blank=True)
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name="journal_entries", null=True, blank=True)
    # Need term for charging not really for other journal_entries
class Payment(models.Model):

    PAYMENT_METHOD_CHOICES = [
        ("mpesa", "M-Pesa/Mobile Money"),
        ("cash", "Cash"),
        ("cheque", "Cheque"),
        ("other", "Other")
    ]
    PAYMENT_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("completed", "Completed"),
        ("failed", "Failed"),
        ("reversed", "Reversed"),
    ]

    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=50, choices=PAYMENT_METHOD_CHOICES, blank=True)
    status = models.CharField(max_length=50, choices=PAYMENT_STATUS_CHOICES, blank=True, default="paid")
    reference = models.CharField(max_length=100, blank=True, unique=True)
    paid_on = models.DateTimeField(auto_now_add=True, blank=True, null=True)
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="payments")
    journal_entry = models.OneToOneField(JournalEntry, on_delete=models.PROTECT, related_name="payment")

class JournalLine(models.Model):
    journal_entry = models.ForeignKey(JournalEntry, on_delete=models.PROTECT, related_name="lines")
    account = models.ForeignKey(Account, on_delete=models.PROTECT, related_name="lines")
    student = models.ForeignKey(Student, null=True, blank=True, on_delete=models.PROTECT, related_name="journal_lines")
    debit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)
    credit = models.DecimalField(max_digits=10, decimal_places=2, default=0.00)

    class Meta:
        constraints = [
            models.CheckConstraint(
                check=(
                    models.Q(debit__gt=Decimal("0.00"), credit__exact=Decimal("0.00")) |
                        models.Q(debit__exact=Decimal("0.00"), credit__gt=Decimal("0.00"))
                ),
                name="debit_or_credit_not_both"
            )
        ]

    def __str__(self):
        side = f"DR {self.debit}" if self.debit else f"CR {self.credit}"
        return side

class StudentTermCharge(models.Model):
    student = models.ForeignKey(Student, on_delete=models.PROTECT, related_name="student")
    # NOTE: term for journal_entry and this term have to be the same, student too
    term = models.ForeignKey(Term, on_delete=models.PROTECT, related_name="student_charge")
    journal_entry = models.OneToOneField(JournalEntry, on_delete=models.PROTECT)
    amount = models.DecimalField(max_digits=10, decimal_places=2)
