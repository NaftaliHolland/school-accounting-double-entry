from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (AcademicYearViewSet, FeeItemViewSet, FeeScheduleViewSet,
                    GradeViewSet, StudentViewSet, TermViewSet)

router = DefaultRouter()

router.register(r"academic-years", AcademicYearViewSet, basename="academic-year")
router.register(r"terms", TermViewSet, basename="term")
router.register(r"grades", GradeViewSet, basename="grade")
router.register(r"fee-items", FeeItemViewSet, basename="fee-item")
router.register(r"fee-schedules", FeeScheduleViewSet, basename="fee-schedule")
router.register(r"students", StudentViewSet, basename="student")

urlpatterns = router.urls
