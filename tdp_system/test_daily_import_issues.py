import unittest
from .daily_import_issues import issue_details


class IssueDetailsTests(unittest.TestCase):
    def test_real_excel_row_column_and_no_identity_fields(self):
        rows=[{'source_row':90,'product_code':'I000067','product_name':'Khế chua',
               'kitchen':'B1','cccd':'PRIVATE-ID','seller':'PRIVATE-SELLER',
               '_issue_columns':{'tax':12},'errors':['Thuế suất chỉ nhận 0%, 5%, 8%, 10%, KCT hoặc KKKNT'],
               'warnings':[]}]
        result=issue_details(rows)
        self.assertEqual(result[0]['cells'],['L90'])
        self.assertEqual(result[0]['row'],90)
        self.assertNotIn('PRIVATE',str(result))

    def test_all_error_rows_including_after_row_200_and_warnings(self):
        rows=[{'source_row':n,'errors':['Giá mua không hợp lệ'],'_issue_columns':{'buy_price':9}} for n in range(3,253)]
        rows.append({'source_row':300,'warnings':['Kiểm tra lại giá']})
        result=issue_details(rows)
        self.assertEqual(len(result),251)
        self.assertEqual(result[-2]['cells'],['I252'])
        self.assertEqual(result[-1]['errors'],[])
