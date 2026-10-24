"""Sprint 3 academic assessment; all objects scoped to tenant + active, validated relationships.

Prototype only: semester rule mapping is configured by school, not a legal transcript engine.
"""
from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied, ValidationError, NotFound
from rest_framework.response import Response
from apps.access.views import TenantAPIView
from apps.academics.models import Classroom, Subject, Enrollment, Student, TeacherAssignment, GuardianLink, StudentAccount
from apps.access.scopes import visible_students
from apps.attendance.models import NotificationOutbox
from apps.attendance.views import lock_school, has_guardian_link
from .models import GradeBook, Assessment, GradeEntry, GradeRevision
from .rules import parse_score, semester_average, qualitative_semester, can_transition

ADMIN = {'SCHOOL_ADMIN','ACADEMIC_AFFAIRS'}
LEADERSHIP = ADMIN | {'PRINCIPAL','VICE_PRINCIPAL'}


def active_assignment(user, tenant, classroom, subject=None, kind='SUBJECT'):
    today = timezone.localdate()
    q = TeacherAssignment.objects.filter(tenant=tenant, teacher=user, classroom=classroom,
          kind=kind, is_active=True, starts_on__lte=today,
          classroom__year__starts_on__lte=today,classroom__year__ends_on__gte=today).filter(Q(ends_on__isnull=True)|Q(ends_on__gte=today))
    if kind == 'SUBJECT': q = q.filter(subject=subject)
    return q.exists()


def grader(view, book):
    return bool(ADMIN & view.roles) or ('SUBJECT_TEACHER' in view.roles and
        active_assignment(view.request.user, view.tenant, book.classroom, book.subject))


def homeroom(view, book):
    return 'HOMEROOM_TEACHER' in view.roles and active_assignment(
        view.request.user,view.tenant,book.classroom,kind='HOMEROOM')


def can_read_book(view, book):
    return bool(LEADERSHIP & view.roles) or grader(view,book) or homeroom(view,book)


def roster(book):
    today = timezone.localdate()
    return Student.objects.filter(tenant=book.tenant,is_active=True, enrollments__tenant=book.tenant,
        enrollments__classroom=book.classroom, enrollments__is_active=True,
        enrollments__starts_on__lte=today).filter(
        Q(enrollments__ends_on__isnull=True)|Q(enrollments__ends_on__gte=today)).distinct().order_by('student_code')


def book_json(book):
    return {'id':str(book.id),'classroom_id':str(book.classroom_id),'classroom_code':book.classroom.code,
        'subject_id':str(book.subject_id),'subject_name':book.subject.name,'semester':book.semester,
        'mode':book.mode,'regular_required':book.regular_required}


def assessment_json(item, include_rows=False):
    obj={'id':str(item.id),'book_id':str(item.book_id),'kind':item.kind,'slot':item.slot,
         'title':item.title,'state':item.state}
    if include_rows:
        data={entry.student_id:entry for entry in item.entries.filter(tenant=item.tenant)}
        pupils=roster(item.book) if item.state=='DRAFT' else Student.objects.filter(tenant=item.tenant,id__in=data).order_by('student_code')
        obj['entries']=[{'id':str(data[s.id].id) if s.id in data else None,
           'student_id':str(s.id),'student_code':s.student_code,'full_name':s.full_name,
           'score':str(data[s.id].score) if s.id in data and data[s.id].score is not None else None,
           'result':data[s.id].result if s.id in data else '',
           'version':data[s.id].version if s.id in data else 0}
           for s in pupils]
    return obj


def serialize_entry_value(mode, data):
    """Validate mode-specific field; explicit EXEMPT is a separate qualitative value."""
    if mode == 'SCORE':
        if data.get('result') not in (None,''):
            raise ValidationError({'result':'Môn điểm số không chấp nhận kết quả nhận xét.'})
        try: score=parse_score(data.get('score'))
        except ValueError as exc: raise ValidationError({'score':str(exc)})
        return score, ''
    if data.get('score') is not None:
        raise ValidationError({'score':'Môn nhận xét không chấp nhận điểm số.'})
    result = data.get('result')
    if result not in ('PASS','FAIL','EXEMPT'):
        raise ValidationError({'result':'Chỉ chấp nhận PASS, FAIL hoặc EXEMPT.'})
    return None,result


class BookCreateSerializer(serializers.Serializer):
    classroom_id=serializers.UUIDField()
    subject_id=serializers.UUIDField()
    semester=serializers.ChoiceField(choices=GradeBook.Semester.choices)
    mode=serializers.ChoiceField(choices=GradeBook.Mode.choices)
    regular_required=serializers.IntegerField(min_value=2,max_value=4)
    def validate(self,data):
        if data['mode']=='COMMENT' and data['regular_required']!=2:
            raise serializers.ValidationError({'regular_required':'Môn nhận xét cần 2 lần đánh giá thường xuyên.'})
        return data


class AssessmentCreateSerializer(serializers.Serializer):
    kind=serializers.ChoiceField(choices=Assessment.Kind.choices)
    slot=serializers.IntegerField(min_value=1,max_value=4,default=1)
    title=serializers.CharField(max_length=140,min_length=2)


class EntryRowSerializer(serializers.Serializer):
    student_id=serializers.UUIDField()
    score=serializers.DecimalField(max_digits=3,decimal_places=1,min_value=0,max_value=10,required=False,allow_null=True)
    result=serializers.CharField(max_length=8,allow_blank=True,required=False)


class EntryBatchSerializer(serializers.Serializer):
    entries=EntryRowSerializer(many=True,allow_empty=False)


class RevisionCreateSerializer(serializers.Serializer):
    score=serializers.DecimalField(max_digits=3,decimal_places=1,min_value=0,max_value=10,required=False,allow_null=True)
    result=serializers.CharField(max_length=8,allow_blank=True,required=False)
    reason=serializers.CharField(min_length=10,max_length=500)


class DecisionSerializer(serializers.Serializer):
    action=serializers.ChoiceField(choices=['approve','reject'])
    decision_note=serializers.CharField(max_length=500,allow_blank=True,required=False)


class BookListCreate(TenantAPIView):
    def get(self,request):
        books=GradeBook.objects.filter(tenant=self.tenant).select_related('classroom','subject')
        if not (LEADERSHIP & self.roles):
            ids=[]
            for book in books:
                if can_read_book(self,book):ids.append(book.pk)
            books=books.filter(pk__in=ids)
        return Response([book_json(x) for x in books.order_by('classroom__code','subject__name','semester')[:200]])

    @transaction.atomic
    def post(self,request):
        lock_school(self.tenant)
        if not (ADMIN & self.roles):raise PermissionDenied('Chỉ giáo vụ/quản trị trường được cấu hình sổ điểm.')
        s=BookCreateSerializer(data=request.data);s.is_valid(raise_exception=True)
        data=s.validated_data
        classroom=get_object_or_404(Classroom,tenant=self.tenant,pk=data['classroom_id'])
        subject=get_object_or_404(Subject,tenant=self.tenant,pk=data['subject_id'])
        if GradeBook.objects.filter(tenant=self.tenant,classroom=classroom,subject=subject,semester=data['semester']).exists():
            raise ValidationError({'detail':'Sổ điểm đã tồn tại.'})
        book=GradeBook.objects.create(tenant=self.tenant,classroom=classroom,subject=subject,
               semester=data['semester'],mode=data['mode'],regular_required=data['regular_required'])
        self.audit(action='GRADEBOOK_CREATED',instance=book)
        return Response(book_json(book),status=status.HTTP_201_CREATED)


class BookDetail(TenantAPIView):
    def get(self,request,book_id):
        book=get_object_or_404(GradeBook.objects.select_related('classroom','subject'),tenant=self.tenant,pk=book_id)
        if not can_read_book(self,book):raise PermissionDenied('Không thuộc lớp/môn được phân công.')
        all_states=bool(LEADERSHIP & self.roles) or grader(self,book)
        items=book.assessments.filter(tenant=self.tenant)
        if not all_states:items=items.filter(state='PUBLISHED')
        out=book_json(book);out['can_edit']=grader(self,book)
        out['assessments']=[assessment_json(item,include_rows=True) for item in items.order_by('kind','slot')]
        return Response(out)


class AssessmentCreate(TenantAPIView):
    @transaction.atomic
    def post(self,request,book_id):
        lock_school(self.tenant)
        book=get_object_or_404(GradeBook,tenant=self.tenant,pk=book_id)
        if not grader(self,book):raise PermissionDenied('Chỉ giáo viên môn được phân công hoặc giáo vụ.')
        s=AssessmentCreateSerializer(data=request.data);s.is_valid(raise_exception=True)
        d=s.validated_data
        if d['kind']!='TX' and d['slot']!=1:
            raise ValidationError({'slot':'Giữa kỳ/cuối kỳ chỉ có slot 1.'})
        if d['kind']=='TX' and d['slot']>book.regular_required:
            raise ValidationError({'slot':'Vượt số cột điểm thường xuyên đã cấu hình.'})
        if Assessment.objects.filter(book=book,kind=d['kind'],slot=d['slot']).exists():
            raise ValidationError({'detail':'Loại/slot đánh giá đã tồn tại.'})
        item=Assessment.objects.create(tenant=self.tenant,book=book,created_by=request.user,**d)
        self.audit(action='ASSESSMENT_CREATED',instance=item)
        return Response(assessment_json(item),status=status.HTTP_201_CREATED)


class EntriesBatch(TenantAPIView):
    @transaction.atomic
    def put(self,request,assessment_id):
        lock_school(self.tenant)
        item=get_object_or_404(Assessment.objects.select_for_update().select_related('book'),tenant=self.tenant,pk=assessment_id)
        if not grader(self,item.book):raise PermissionDenied('Không được nhập điểm môn này.')
        if item.state!='DRAFT':raise ValidationError({'detail':'Cột điểm đã khóa.'})
        s=EntryBatchSerializer(data=request.data);s.is_valid(raise_exception=True)
        rows=s.validated_data['entries']
        ids=[r['student_id'] for r in rows]
        if len(ids)!=len(set(ids)):raise ValidationError({'entries':'Học sinh trùng trong batch.'})
        valid_ids=set(roster(item.book).values_list('id',flat=True))
        if not set(ids)<=valid_ids:raise ValidationError({'entries':'Học sinh không thuộc lớp hiện tại.'})
        validated=[(r['student_id'],*serialize_entry_value(item.book.mode,r)) for r in rows]
        if any(result=='EXEMPT' for _,_,result in validated) and not (ADMIN & self.roles):
            raise PermissionDenied('Đánh giá Miễn chỉ do giáo vụ/quản trị nhập sau khi xác minh hồ sơ.')
        for student_id,score,result in validated:
            entry,_=GradeEntry.objects.select_for_update().get_or_create(tenant=self.tenant,
               assessment=item,student_id=student_id,defaults={'score':score,'result':result,'updated_by':request.user})
            if not _:entry.score=score;entry.result=result;entry.version+=1;entry.updated_by=request.user;entry.save()
        self.audit(action='GRADE_ENTRIES_SAVED',instance=item)
        return Response({'updated':len(validated),'state':item.state})


class AssessmentLock(TenantAPIView):
    @transaction.atomic
    def post(self,request,assessment_id):
        lock_school(self.tenant)
        item=get_object_or_404(Assessment.objects.select_for_update().select_related('book'),tenant=self.tenant,pk=assessment_id)
        if not grader(self,item.book):raise PermissionDenied('Chỉ giáo viên môn được phân công hoặc giáo vụ.')
        if not can_transition(item.state,'LOCKED'):
            raise ValidationError({'detail':'Chỉ khóa cột điểm ở trạng thái DRAFT.'})
        expected=set(roster(item.book).values_list('id',flat=True))
        present=set(item.entries.values_list('student_id',flat=True))
        if not expected or expected!=present:raise ValidationError({'detail':'Phải có đầy đủ đánh giá cho mọi học sinh đang học.'})
        item.state='LOCKED';item.locked_at=timezone.now();item.save(update_fields=['state','locked_at'])
        self.audit(action='ASSESSMENT_LOCKED',instance=item)
        return Response(assessment_json(item))


class AssessmentPublish(TenantAPIView):
    @transaction.atomic
    def post(self,request,assessment_id):
        lock_school(self.tenant)
        if not (ADMIN & self.roles):raise PermissionDenied('Chỉ quản trị trường/giáo vụ được công bố.')
        item=get_object_or_404(Assessment.objects.select_for_update().select_related('book'),tenant=self.tenant,pk=assessment_id)
        if not can_transition(item.state,'PUBLISHED'):
            raise ValidationError({'detail':'Chỉ công bố cột điểm LOCKED.'})
        item.state='PUBLISHED';item.published_at=timezone.now();item.save(update_fields=['state','published_at'])
        self.audit(action='ASSESSMENT_PUBLISHED',instance=item)
        # Outbox records are generated, not sent. No personal scores in payload.
        today=timezone.localdate()
        guardians=GuardianLink.objects.filter(tenant=self.tenant,is_active=True,is_verified=True,
            can_view_academic=True,valid_from__lte=today,
            student_id__in=item.entries.values_list('student_id',flat=True)).filter(
            Q(valid_to__isnull=True)|Q(valid_to__gte=today))
        for link in guardians:
            NotificationOutbox.objects.get_or_create(dedupe_key=f'grade-pub:{item.pk}:{link.guardian_id}',defaults={
                'tenant':self.tenant,'recipient':link.guardian,'event_type':'GRADE_PUBLISHED',
                'subject_id':item.pk,'payload':{'assessment_id':str(item.pk)}})
        return Response(assessment_json(item))


class StudentGrades(TenantAPIView):
    def get(self,request,student_id):
        student=get_object_or_404(visible_students(request.user,self.tenant,self.roles),pk=student_id)
        # Do not let subject teachers use the Student endpoint to enumerate other subjects.
        all_subjects=bool(LEADERSHIP & self.roles)
        books=GradeBook.objects.filter(tenant=self.tenant,
          classroom_id__in=Enrollment.objects.filter(tenant=self.tenant,student=student).values('classroom_id'))
        result=[]
        for book in books.select_related('classroom','subject'):
            if not all_subjects and not (
                'PARENT' in self.roles and has_guardian_link(request.user,self.tenant,student) or
                'STUDENT' in self.roles and StudentAccount.objects.filter(tenant=self.tenant,student=student,account=request.user).exists() or
                homeroom(self,book) or grader(self,book)):
                continue
            # Only published values in this endpoint, including for staff.
            assessments=Assessment.objects.filter(tenant=self.tenant,book=book,state='PUBLISHED')
            rows=[];scores={};qual={}
            for item in assessments:
                entry=GradeEntry.objects.filter(assessment=item,student=student,tenant=self.tenant).first()
                if not entry:continue
                rows.append({'kind':item.kind,'slot':item.slot,'title':item.title,
                    'score':str(entry.score) if entry.score is not None else None,'result':entry.result})
                key=(item.kind,item.slot)
                if entry.score is not None:scores[key]=entry.score
                if entry.result:qual[key]=entry.result
            regular=[scores[('TX',idx)] for idx in range(1,book.regular_required+1) if ('TX',idx) in scores]
            average=semester_average(regular,scores.get(('GK',1)),scores.get(('CK',1)),book.regular_required) if book.mode=='SCORE' else None
            observation=[qual[k] for k in [('TX',1),('TX',2),('GK',1),('CK',1)] if k in qual]
            classification=qualitative_semester(observation,book.regular_required) if book.mode=='COMMENT' else None
            if not rows:
                continue
            result.append({**book_json(book),'assessments':rows,'semester_average':str(average) if average is not None else None,
                           'semester_result':classification})
        return Response({'student_id':str(student.id),'student_name':student.full_name,'books':result})


class RevisionCreate(TenantAPIView):
    @transaction.atomic
    def post(self,request,entry_id):
        lock_school(self.tenant)
        entry=get_object_or_404(GradeEntry.objects.select_for_update().select_related('assessment__book'),tenant=self.tenant,pk=entry_id)
        if not grader(self,entry.assessment.book):raise PermissionDenied('Không được yêu cầu sửa điểm môn này.')
        if entry.assessment.state not in ('LOCKED','PUBLISHED'):
            raise ValidationError({'detail':'Chỉ dùng yêu cầu điều chỉnh sau khi khóa/công bố.'})
        s=RevisionCreateSerializer(data=request.data);s.is_valid(raise_exception=True)
        value=serialize_entry_value(entry.assessment.book.mode,s.validated_data)
        if value[1]=='EXEMPT' and not (ADMIN & self.roles):
            raise PermissionDenied('Đề nghị xác nhận Miễn phải được giáo vụ xử lý.')
        if value==(entry.score,entry.result):raise ValidationError({'detail':'Kết quả mới trùng kết quả hiện tại.'})
        if GradeRevision.objects.filter(entry=entry,state='PENDING').exists():
            raise ValidationError({'detail':'Đã có yêu cầu điều chỉnh đang chờ.'})
        rev=GradeRevision.objects.create(tenant=self.tenant,entry=entry,from_version=entry.version,
          old_score=entry.score,old_result=entry.result,proposed_score=value[0],proposed_result=value[1],
          reason=s.validated_data['reason'],requested_by=request.user)
        self.audit(action='GRADE_REVISION_REQUESTED',instance=rev)
        return Response({'id':str(rev.id),'state':rev.state},status=status.HTTP_201_CREATED)


class RevisionList(TenantAPIView):
    def get(self,request):
        revisions=GradeRevision.objects.filter(tenant=self.tenant).select_related('entry__student','entry__assessment__book__classroom','entry__assessment__book__subject').order_by('-created_at')
        if not (ADMIN & self.roles):
            revisions=[r for r in revisions if grader(self,r.entry.assessment.book)]
        return Response([{'id':str(r.id),'entry_id':str(r.entry_id),'state':r.state,
             'reason':r.reason,'from_version':r.from_version,'old_result':r.old_result,
             'student_name':r.entry.student.full_name,'classroom_code':r.entry.assessment.book.classroom.code,
             'subject_name':r.entry.assessment.book.subject.name,'assessment_title':r.entry.assessment.title,
             'decision_note':r.decision_note,
             'old_score':str(r.old_score) if r.old_score is not None else None,
             'proposed_score':str(r.proposed_score) if r.proposed_score is not None else None,
             'proposed_result':r.proposed_result} for r in list(revisions)[:200]])


class RevisionDecision(TenantAPIView):
    @transaction.atomic
    def post(self,request,revision_id):
        lock_school(self.tenant)
        if not (ADMIN & self.roles):raise PermissionDenied('Chỉ quản trị/giáo vụ xử lý điều chỉnh.')
        rev=get_object_or_404(GradeRevision.objects.select_for_update(),tenant=self.tenant,pk=revision_id)
        if rev.state!='PENDING':raise ValidationError({'detail':'Yêu cầu đã xử lý.'})
        s=DecisionSerializer(data=request.data);s.is_valid(raise_exception=True)
        entry=GradeEntry.objects.select_for_update().get(pk=rev.entry_id,tenant=self.tenant)
        if s.validated_data['action']=='approve' and entry.version!=rev.from_version:
            raise ValidationError({'detail':'Dữ liệu đã thay đổi. Cần tạo yêu cầu mới.'})
        if s.validated_data['action']=='approve':
            entry.score=rev.proposed_score;entry.result=rev.proposed_result
            entry.version+=1;entry.updated_by=request.user
            entry.save(update_fields=['score','result','version','updated_by','updated_at'])
            rev.state='APPROVED'
        else: rev.state='REJECTED'
        rev.decided_by=request.user;rev.decided_at=timezone.now()
        rev.decision_note=s.validated_data.get('decision_note','')
        rev.save(update_fields=['state','decided_by','decided_at','decision_note'])
        self.audit(action='GRADE_REVISION_'+rev.state,instance=rev)
        if rev.state=='APPROVED' and entry.assessment.state=='PUBLISHED':
            today=timezone.localdate()
            links=GuardianLink.objects.filter(tenant=self.tenant,student=entry.student,
                student__is_active=True,is_active=True,is_verified=True,can_view_academic=True,valid_from__lte=today).filter(
                Q(valid_to__isnull=True)|Q(valid_to__gte=today))
            for link in links:
                NotificationOutbox.objects.get_or_create(dedupe_key=f'grade-revision:{rev.pk}:{link.guardian_id}',defaults={
                    'tenant':self.tenant,'recipient':link.guardian,'event_type':'GRADE_CORRECTED',
                    'subject_id':rev.pk,'payload':{'revision_id':str(rev.pk),'assessment_id':str(entry.assessment_id)}})
        # If approved, published score becomes visible immediately with traceable revision version.
        return Response({'id':str(rev.id),'state':rev.state,'entry_version':entry.version})
