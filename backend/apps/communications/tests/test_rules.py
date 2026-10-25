import unittest, uuid
from apps.communications.rules import validate_body,validate_key,valid_ticket_transition,valid_notice

class PureCommunicationRules(unittest.TestCase):
    def test_body(self):
        self.assertEqual(validate_body('  Xin chào  '),'Xin chào')
        for b in ['', '  ',None,'x'*5001]:
            with self.assertRaises(ValueError):validate_body(b)
    def test_client_key(self):
        key=str(uuid.uuid4());self.assertEqual(validate_key(key),key)
        for k in ['', 'hello', 'x'*100]:
            with self.assertRaises(ValueError):validate_key(k)
    def test_ticket_transitions(self):
        self.assertTrue(valid_ticket_transition('OPEN','IN_PROGRESS',True))
        self.assertFalse(valid_ticket_transition('OPEN','CLOSED',True))
        self.assertFalse(valid_ticket_transition('OPEN','RESOLVED',False))
        self.assertTrue(valid_ticket_transition('IN_PROGRESS','RESOLVED',True))
        self.assertTrue(valid_ticket_transition('RESOLVED','CLOSED',True))
        self.assertFalse(valid_ticket_transition('CLOSED','OPEN',True))
    def test_scope_validation(self):
        self.assertTrue(valid_notice('SCHOOL',None,None))
        self.assertTrue(valid_notice('GRADE',None,8))
        self.assertTrue(valid_notice('CLASS',str(uuid.uuid4()),None))
        self.assertFalse(valid_notice('GRADE',None,10))
        self.assertFalse(valid_notice('CLASS',None,None))
        self.assertFalse(valid_notice('SCHOOL','id',None))

if __name__=='__main__':unittest.main()
