from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from django.shortcuts import render, get_object_or_404
from django.db.models import Q
from .models import PetReport, Notification
from .serializers import PetReportSerializer, PetReportStatusSerializer, NotificationSerializer

def report_form_page(request):
    return render(request, 'pets/report_form.html')

def pet_list_page(request):
    return render(request, 'pets/pet_list.html')

def admin_dashboard_page(request):
    return render(request, 'pets/admin_dashboard.html')

def admin_login_page(request):
    return render(request, 'pets/admin_login.html')

def my_reports_page(request):
    return render(request, 'pets/my_reports.html')

def search_page(request):
    return render(request, 'pets/search.html')

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def create_report(request):
    serializer = PetReportSerializer(data=request.data)
    if serializer.is_valid():
        report = serializer.save(user=request.user)
        # Create admin notification
        Notification.objects.create(
            user=request.user,
            message=f"New {report.report_type} pet report submitted by {request.user.email} for a {report.pet_type}.",
            notif_type='report_submitted',
            report=report
        )
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def list_reports(request):
    report_type = request.query_params.get('type')
    pet_type = request.query_params.get('pet_type')
    color = request.query_params.get('color')
    location = request.query_params.get('location')
    breed = request.query_params.get('breed')

    qs = PetReport.objects.filter(status='accepted')
    if report_type:
        qs = qs.filter(report_type=report_type)
    if pet_type:
        qs = qs.filter(pet_type=pet_type)
    if color:
        qs = qs.filter(color__icontains=color)
    if location:
        qs = qs.filter(location__icontains=location)
    if breed:
        qs = qs.filter(breed__icontains=breed)

    return Response(PetReportSerializer(qs, many=True, context={'request': request}).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def my_reports(request):
    reports = PetReport.objects.filter(user=request.user)
    return Response(PetReportSerializer(reports, many=True, context={'request': request}).data)

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def search_matching_pets(request):
    pet_type = request.query_params.get('pet_type')
    color = request.query_params.get('color')
    location = request.query_params.get('location')
    breed = request.query_params.get('breed')

    if not pet_type:
        return Response({'error': 'pet_type is required'}, status=status.HTTP_400_BAD_REQUEST)

    qs = PetReport.objects.filter(status='accepted', report_type='found')

    results = []
    for report in qs:
        score = 0

        # Match pet_type — also match if report pet_type is 'other' when searching 'other'
        if report.pet_type == pet_type:
            score += 40
        elif pet_type == 'other' and report.pet_type not in ['dog', 'cat', 'bird']:
            score += 40

        if color and color.lower() in report.color.lower():
            score += 25
        if location and location.lower() in report.location.lower():
            score += 20
        if breed and breed.lower() in (report.breed or '').lower():
            score += 15

        if score >= 40:
            results.append((score, report))

    results.sort(key=lambda x: x[0], reverse=True)
    sorted_reports = [r for _, r in results]

    return Response({
        'count': len(sorted_reports),
        'results': PetReportSerializer(sorted_reports, many=True, context={'request': request}).data
    })

# Admin views
@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_all_reports(request):
    status_filter = request.query_params.get('status', 'pending')
    reports = PetReport.objects.filter(status=status_filter).order_by('-created_at')
    return Response(PetReportSerializer(reports, many=True, context={'request': request}).data)

@api_view(['PATCH'])
@permission_classes([IsAdminUser])
def update_report_status(request, pk):
    report = get_object_or_404(PetReport, pk=pk)
    status_value = request.data.get("status")

    if not status_value:
        return Response({"error": "Status is required"}, status=status.HTTP_400_BAD_REQUEST)

    status_value = status_value.lower()
    if status_value not in ["pending", "accepted", "rejected"]:
        return Response({"error": "Invalid status."}, status=status.HTTP_400_BAD_REQUEST)

    report.status = status_value
    report.admin_note = request.data.get("admin_note", report.admin_note)
    report.save()

    # Notify the user about status update
    Notification.objects.create(
        user=report.user,
        message=f"Your {report.report_type} pet report for a {report.pet_type} has been {status_value}. {report.admin_note or ''}",
        notif_type='status_updated',
        report=report
    )

    return Response({"message": "Status updated successfully", "new_status": report.status})

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def user_notifications(request):
    notifications = Notification.objects.filter(
        user=request.user,
        notif_type='status_updated'
    ).order_by('-created_at')
    serializer = NotificationSerializer(notifications, many=True)
    return Response(serializer.data)

@api_view(['GET'])
@permission_classes([IsAdminUser])
def admin_notifications(request):
    notifications = Notification.objects.filter(
        notif_type='report_submitted'
    ).order_by('-created_at')
    unread_count = notifications.filter(is_read=False).count()
    return Response({
        'unread_count': unread_count,
        'notifications': NotificationSerializer(notifications, many=True).data
    })

@api_view(['POST'])
@permission_classes([IsAdminUser])
def mark_notifications_read(request):
    Notification.objects.filter(notif_type='report_submitted', is_read=False).update(is_read=True)
    return Response({'message': 'Notifications marked as read'})

@api_view(['POST'])
@permission_classes([IsAuthenticated])
def mark_user_notifications_read(request):
    Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    return Response({'message': 'Notifications marked as read'})