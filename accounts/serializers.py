from rest_framework import serializers

from .models import (AcademicYear, Account, FeeItem, FeeSchedule, Grade,
                     JournalEntry, JournalLine, Payment, Student, Term)


class AcademicYearSerializer(serializers.ModelSerializer):

    class Meta:
        model = AcademicYear
        fields = [
            'id',
            'label',
        ]

        read_only_fields = ['id',]

class TermSerializer(serializers.ModelSerializer):

    class Meta:
        model = Term 
        fields = [
            'id',
            'academic_year',
            'name',
            'start_date',
            'end_date',
            'status',
            'locked_at',
        ]

        read_only_fields = ['id',]

class GradeSerializer(serializers.ModelSerializer):
     class Meta:
        model = Grade
        fields = [
            'id',
            'name',
        ]

        read_only_fields = ['id',]


class FeeItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeItem
        fields = [
            'id',
            'name',
            'description',
        ]
        read_only_fields = ['id',]

class FeeScheduleSerializer(serializers.ModelSerializer):
    class Meta:
        model = FeeSchedule
        fields = [
            'id',
            'grade',
            'fee_item',
            'term',
            'amount'
        ]

        read_only_fields = ['id',]


class StudentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Student
        fields = [
            'id',
            'name',
            'grade',
        ]

        read_only_fields = ['id',]


class AccountSerializer(serializers.ModelSerializer):
    class Meta:
        model = Account
        fields = [
            'id',
            'name',
            'type',
            'normal_side',
        ]
        read_only_fields = ['id',]


class JournalEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = JournalEntry
        fields = [
            'id',
            'created_at',
            'description',
            'reference',
            'term',
        ]
        read_only_fields = ['id', 'created_at',]


class JournalLine(serializers.ModelSerializer):
    class Meta:
        model = JournalLine
        fields = [
            'id',
            'journal_entry',
            'account',
            'student',
            'debit',
            'credit'
        ]
        read_only_fields = ['id']


class PaymentInputSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    payment_method = serializers.ChoiceField(choices=Payment.PAYMENT_METHOD_CHOICES, allow_blank=True)
    reference = serializers.CharField()
    paid_on = serializers.DateTimeField()

class PaymentSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payment
        fields = [
            "id",
            "amount",
            "payment_method",
            "status",
            "reference",
            "paid_on",
            "student",
            "journal_entry"
        ]
