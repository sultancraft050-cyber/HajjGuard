import json
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.views.decorators.http import require_GET, require_POST
from .models import AuditLog, GuardianRelationship, PilgrimProfile


@login_required(login_url='/accounts/login/')
@require_POST
def create_relationship(request):
    guardian = getattr(request.user, 'profile', None)
    try:
        data = json.loads(request.body or '{}')
        dependent_id = int(data['dependent_id'])
        relationship_type = str(data.get('relationship_type', 'CAREGIVER'))
    except (KeyError, TypeError, ValueError, json.JSONDecodeError):
        return JsonResponse({'status': 'error', 'message': 'Invalid guardian relationship.'}, status=400)
    dependent = PilgrimProfile.objects.filter(id=dependent_id).first()
    if not guardian or not dependent or guardian.id == dependent.id:
        return JsonResponse({'status': 'error', 'message': 'Valid guardian and dependent are required.'}, status=400)
    row, _ = GuardianRelationship.objects.get_or_create(guardian=guardian, dependent=dependent, defaults={'relationship_type': relationship_type})
    row.relationship_type = relationship_type
    row.guardian_approved = True
    row.consent_given = False
    row.save(update_fields=['relationship_type', 'guardian_approved', 'consent_given'])
    AuditLog.objects.create(user=request.user, action='VIEW_PILGRIM', target=f'GUARDIAN_RELATIONSHIP_CREATED dependent={dependent.id}', ip_address=request.META.get('REMOTE_ADDR'))
    return JsonResponse({'status': 'pending', 'relationship_id': row.id, 'dependent_approval_required': True})


@login_required(login_url='/accounts/login/')
@require_POST
def approve_relationship(request, relationship_id):
    row = GuardianRelationship.objects.filter(id=relationship_id).select_related('guardian__user', 'dependent__user').first()
    if not row:
        return JsonResponse({'status': 'error', 'message': 'Relationship not found.'}, status=404)
    profile = getattr(request.user, 'profile', None)
    if profile == row.guardian:
        row.guardian_approved = True
    elif profile == row.dependent:
        row.dependent_approved = True
    else:
        return JsonResponse({'status': 'error', 'message': 'Relationship access denied.'}, status=403)
    if row.guardian_approved and row.dependent_approved:
        row.consent_given = True
        row.consent_timestamp = timezone.now()
    row.save(update_fields=['guardian_approved', 'dependent_approved', 'consent_given', 'consent_timestamp'])
    return JsonResponse({'status': 'success', 'active': row.active})


@login_required(login_url='/accounts/login/')
@require_GET
def relationships(request):
    profile = getattr(request.user, 'profile', None)
    rows = GuardianRelationship.objects.filter(guardian=profile) | GuardianRelationship.objects.filter(dependent=profile)
    return JsonResponse({'status': 'success', 'relationships': [{'id': r.id, 'guardian_id': r.guardian_id, 'dependent_id': r.dependent_id, 'active': r.active} for r in rows.distinct()]})
