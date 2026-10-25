"""Synthetic demo only. NEVER run in a school database containing real records."""
from datetime import timedelta
from django.core.management.base import BaseCommand, CommandError
from django.conf import settings
from django.db import transaction
from django.utils import timezone
from apps.identity.models import Account
from apps.schools.models import Tenant, Membership
from apps.academics.models import (AcademicYear, Classroom, Subject, Student,
    Enrollment, TeacherAssignment, GuardianLink, StudentAccount)

class Command(BaseCommand):
    help = 'Create two synthetic test tenants and demo actors (dev only).'

    @transaction.atomic
    def handle(self, *args, **kwargs):
        if not settings.DEBUG:
            raise CommandError('seed_demo chỉ được chạy với DJANGO_DEBUG=1.')
        today = timezone.localdate()
        year_start = today - timedelta(days=60)
        year_end = today + timedelta(days=300)
        passwd = 'DemoOnly!ChangeMe123'

        def account(username, label):
            obj, _ = Account.objects.get_or_create(username=username, defaults={'display_name': label})
            if _:
                obj.set_password(passwd)
                obj.save(update_fields=['password'])
            return obj

        def membership(tenant, account_obj, role):
            Membership.objects.get_or_create(tenant=tenant, account=account_obj, role=role,
                defaults={'is_active':True,'valid_from':year_start})

        for prefix, schoolname in [('a','THCS Demo An Bình'),('b','THCS Demo Bình Minh')]:
            tenant, _ = Tenant.objects.get_or_create(code=f'demo-{prefix}', defaults={'name':schoolname})
            year, _ = AcademicYear.objects.get_or_create(tenant=tenant, label='Demo Academic Year',
                defaults={'starts_on':year_start,'ends_on':year_end})
            clazz, _ = Classroom.objects.get_or_create(tenant=tenant, year=year, code='8A1',
                defaults={'grade_level':8})
            subj, _ = Subject.objects.get_or_create(tenant=tenant, code='MATH', defaults={'name':'Toán'})
            stu, _ = Student.objects.get_or_create(tenant=tenant, student_code='HS001',
                defaults={'full_name':f'Học sinh thử nghiệm {prefix.upper()}', 'date_of_birth':today - timedelta(days=14*365)})
            Enrollment.objects.get_or_create(tenant=tenant, student=stu, classroom=clazz,
                defaults={'starts_on':year_start})
            support = account(f'support_{prefix}', f'Hỗ trợ trường {prefix.upper()}')
            membership(tenant, support, 'SUPPORT_STAFF')
            admin = account(f'admin_{prefix}', f'Quản trị trường {prefix.upper()}')
            homeroom = account(f'gvcn_{prefix}', f'GVCN trường {prefix.upper()}')
            subject_teacher = account(f'gvbm_{prefix}', f'GV Toán trường {prefix.upper()}')
            parent = account(f'parent_{prefix}', f'Phụ huynh trường {prefix.upper()}')
            child = account(f'student_{prefix}', f'Học sinh trường {prefix.upper()}')
            for actor, role in [(admin,'SCHOOL_ADMIN'),(homeroom,'HOMEROOM_TEACHER'),
                                (subject_teacher,'SUBJECT_TEACHER'),(parent,'PARENT'),(child,'STUDENT')]:
                membership(tenant, actor, role)
            TeacherAssignment.objects.get_or_create(tenant=tenant, teacher=homeroom, classroom=clazz,
                kind='HOMEROOM', defaults={'starts_on':year_start})
            TeacherAssignment.objects.get_or_create(tenant=tenant, teacher=subject_teacher,
                classroom=clazz, kind='SUBJECT', subject=subj, defaults={'starts_on':year_start})
            GuardianLink.objects.get_or_create(tenant=tenant, student=stu, guardian=parent,
                defaults={'relation':'MOTHER','is_verified':True,'verified_by':admin,'valid_from':year_start})
            StudentAccount.objects.get_or_create(tenant=tenant, student=stu, account=child)
            self.stdout.write(f'{schoolname}: {tenant.id}')
        self.stdout.write(self.style.WARNING('SYNTHETIC DEMO ACCOUNTS; shared dev password: '+passwd))
