from django.test import TestCase
from django.core.cache import cache
from apps.homework.tests import test_api,test_security
from apps.academics.models import GuardianLink,Enrollment
class LegacyInboxTests(TestCase):
    setUpTestData=classmethod(test_api.HomeworkIntegrationTests.setUpTestData.__func__)
    c=test_api.HomeworkIntegrationTests.c
    task=test_api.HomeworkIntegrationTests.task
    published=test_security.HomeworkSecurityTests.published
    submit=test_security.HomeworkSecurityTests.submit
    return_work=test_security.HomeworkSecurityTests.return_work
    def setUp(self):cache.clear()
    def test_homework_event_retains_live_guardian_and_student_scope(self):
        sub=self.submit();self.assertEqual(self.return_work(sub).status_code,200)
        url='/api/v1/comms/notifications/'
        for u in [self.parent,self.pupil]:self.assertEqual(len(self.c(u).get(url).json()),1)
        event=self.c(self.parent).get(url).json()[0]['id']
        GuardianLink.objects.filter(guardian=self.parent).update(is_verified=False)
        self.assertEqual(self.c(self.parent).get(url).json(),[])
        self.assertEqual(self.c(self.parent).post(url+event+'/read/',{},format='json').status_code,404)
        Enrollment.objects.filter(student=self.stu).update(is_active=False)
        self.assertEqual(self.c(self.pupil).get(url).json(),[])
