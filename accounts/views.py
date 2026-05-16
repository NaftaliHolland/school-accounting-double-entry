from django.shortcuts import render
from rest_framework import viewsets

from .models import AcademicYear, Grade, Term
from .serializers import (AcademicYearSerializer, GradeSerializer,
                          TermSerializer)

class AcademicYearViewSet(viewsets.ModelViewSet):
    queryset = AcademicYear.objects.all()
    serializer_class = AcademicYearSerializer

class TermViewSet(viewsets.ModelViewSet):
    queryset = Term.objects.all()
    serializer_class = TermSerializer

class GradeViewSet(viewsets.ModelViewSet):
    queryset = Grade.objects.all()
    serializer_class = GradeSerializer 
