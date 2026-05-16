from django.shortcuts import get_object_or_404, render
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .models import AcademicYear, FeeItem, FeeSchedule, Grade, Student, Term
from .serializers import (AcademicYearSerializer, FeeItemSerializer,
                          FeeScheduleSerializer, GradeSerializer,
                          PaymentInputSerializer, PaymentSerializer,
                          StudentSerializer, TermSerializer)
from .services import charge_student, get_balance, record_payment


class AcademicYearViewSet(viewsets.ModelViewSet):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer

class TermViewSet(viewsets.ModelViewSet):
    queryset = Term.objects.all()
    serializer_class = TermSerializer

    @action(detail=True, methods=["POST"])
    def lock(self, request, pk=None):
        term = self.get_object()
        term.status = "locked"

        term.save()

        return Response({"message": "term locked"})

class GradeViewSet(viewsets.ModelViewSet):
    queryset = Grade.objects.all()
    serializer_class = GradeSerializer 

class FeeScheduleViewSet(viewsets.ModelViewSet):
    queryset = FeeSchedule.objects.all()
    serializer_class = FeeScheduleSerializer

class FeeItemViewSet(viewsets.ModelViewSet):
    queryset = FeeItem.objects.all()
    serializer_class = FeeItemSerializer


class StudentViewSet(viewsets.ModelViewSet):
    queryset = Student
    serializer_class = StudentSerializer

    @action(detail=True, methods=["POST"])
    def charge(self, request, pk=None):
        term_id = request.data.get("term")
        if not term_id:
            return Response({"message": "term required"}, status=status.HTTP_400_BAD_REQUEST)
        
        term = get_object_or_404(Term, pk=term_id)
        student = self.get_object()

        try:
            journal_entry = charge_student(student, term)
        except Exception as e:
            return Response({"error": str(e)})

        return Response({"message": f"Student charged for term {term.name}", "journal_entry_reference" : journal_entry.id})

    @action(detail=True, methods=["GET"])
    def balance(self, request, pk=None):
        student = self.get_object()

        balance = get_balance(student)

        return Response({"balance": balance})


    # Just have a serializer for this so that we don't have to validate everything here, that is the work of the serializer
    @action(detail=True, methods=["POST"])
    def pay(self, request, pk=None):
        serializer = PaymentInputSerializer(data=request.data)
        if serializer.is_valid():
            data = serializer.validated_data

            student = self.get_object()
            try:
                payment = record_payment(
                    student=student,
                    amount=data["amount"],
                    reference=data["reference"],
                    payment_method=data["payment_method"],
                    paid_on=data["paid_on"],
                )
                response_serializer = PaymentSerializer(payment)
                return Response(response_serializer.data)

            except Exception as e:
                message = str(e)
                if "accounts_payment.reference" in message:
                    return Response({"error": "Payment already recorded : duplicate reference"}, status=status.HTTP_400_BAD_REQUEST)
                return Response({"error": message}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
