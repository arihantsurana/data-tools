from unittest import TestCase

from hip_data_tools.etl.google_sheet_to_athena import GoogleSheetToAthena, GoogleSheetsToAthenaSettings


class TestS3Util(TestCase):
    @classmethod
    def setUpClass(cls):
        cls.util = GoogleSheetToAthena(GoogleSheetsToAthenaSettings(
            key_file_path='../resources/key-file.json',
            workbook_name='Tradie Acquisition Targets',
            sheet_name='Sheet1',
            table_name='test_sheets',
            field_names=['Jan_18', 'Feb_18', 'Mar_18', 'Apr_18', 'May_18', 'Jun_18', 'Jul_18', 'Aug_18', 'Sep_18',
                         'Oct_18',
                         'Nov_18', 'Dec_18', 'Jan_19', 'Feb_19', 'Mar_19', 'Apr_19', 'May_19', 'Jun_19', 'Jul_19',
                         'Aug_19',
                         'Sep_19', 'Oct_19', 'Nov_19', 'Dec_19', 'Jan_20', 'Feb_20', 'Mar_20', 'Apr_20', 'May_20',
                         'Jun_20'],
            database='dev',
            # TODO use different bucket
            s3_bucket='au-com-hipages-data-scratchpad',
            s3_dir='sheets',
            skip_top_rows_count=1,
            region='ap-southeast-2',
            profile='default',
            secrets_manager=None
        ))

    @classmethod
    def tearDownClass(cls):
        return

    def integration_test_should__load_sheet_to_athena__when_using_sheetUtil(self):
        self.util.load_sheet_to_athena()

    def test_should__return_the_table_settings__when_using_sheetUtil(self):
        table_name = 'abc'
        field_names = ['Jan-18', 'Feb-18', 'Mar-18', 'Apr-18', 'May-18', 'Jun-18', 'Jul-18', 'Aug-18', 'Sep-18',
                       'Oct-18',
                       'Nov-18', 'Dec-18', 'Jan-19', 'Feb-19', 'Mar-19', 'Apr-19', 'May-19', 'Jun-19', 'Jul-19',
                       'Aug-19',
                       'Sep-19', 'Oct-19', 'Nov-19', 'Dec-19', 'Jan-20', 'Feb-20', 'Mar-20', 'Apr-20', 'May-20',
                       'Jun-20']
        s3_bucket = "test"
        s3_dir = "abc"
        actual = self.util.get_table_settings(table_name, field_names, s3_bucket, s3_dir)
        expected = {
            "table": "abc",
            "exists": True,
            "partitions": [],
            "columns": [
                {'column': 'Jan-18', 'type': 'string'},
                {'column': 'Feb-18', 'type': 'string'},
                {'column': 'Mar-18', 'type': 'string'},
                {'column': 'Apr-18', 'type': 'string'},
                {'column': 'May-18', 'type': 'string'},
                {'column': 'Jun-18', 'type': 'string'},
                {'column': 'Jul-18', 'type': 'string'},
                {'column': 'Aug-18', 'type': 'string'},
                {'column': 'Sep-18', 'type': 'string'},
                {'column': 'Oct-18', 'type': 'string'},
                {'column': 'Nov-18', 'type': 'string'},
                {'column': 'Dec-18', 'type': 'string'},
                {'column': 'Jan-19', 'type': 'string'},
                {'column': 'Feb-19', 'type': 'string'},
                {'column': 'Mar-19', 'type': 'string'},
                {'column': 'Apr-19', 'type': 'string'},
                {'column': 'May-19', 'type': 'string'},
                {'column': 'Jun-19', 'type': 'string'},
                {'column': 'Jul-19', 'type': 'string'},
                {'column': 'Aug-19', 'type': 'string'},
                {'column': 'Sep-19', 'type': 'string'},
                {'column': 'Oct-19', 'type': 'string'},
                {'column': 'Nov-19', 'type': 'string'},
                {'column': 'Dec-19', 'type': 'string'},
                {'column': 'Jan-20', 'type': 'string'},
                {'column': 'Feb-20', 'type': 'string'},
                {'column': 'Mar-20', 'type': 'string'},
                {'column': 'Apr-20', 'type': 'string'},
                {'column': 'May-20', 'type': 'string'},
                {'column': 'Jun-20', 'type': 'string'}
            ],
            "storage_format_selector": "parquet",
            "s3_bucket": "test",
            "s3_dir": "abc",
            "encryption": False
        }
        self.assertEqual(actual, expected)

    def test_should__return_the_insert_query__when_using_sheetUtil(self):
        table_name = "test_table"
        values_matix = [
            ['4,092', '3,192', '3,192', '2,800', '3,015', '3,015', '3,100', '3,415', '3,600', '3,570', '3,210',
             '1,900', '3,100', '2,747', '2,631', '2,419', '2,769', '3,163', '2,792', '3,018', '2,920', '3,541',
             '3,128', '2,020', '3,678', '3,522', '3,534', '3,078', '3,114', '3,206'],
            ['6,343', '4,192', '9,192', '2,800', '3,015', '3,015', '3,100', '3,415', '3,600', '3,570', '3,210',
             '1,900', '3,100', '2,747', '2,631', '2,419', '2,769', '3,163', '2,792', '3,018', '2,920', '3,541',
             '3,128', '2,020', '3,678', '3,522', '3,534', '3,078', '3,114', '8,206']]
        expected = """
                INSERT INTO test_table VALUES ('4,092', '3,192', '3,192', '2,800', '3,015', '3,015', '3,100', '3,415', '3,600', '3,570', '3,210', '1,900', '3,100', '2,747', '2,631', '2,419', '2,769', '3,163', '2,792', '3,018', '2,920', '3,541', '3,128', '2,020', '3,678', '3,522', '3,534', '3,078', '3,114', '3,206'), ('6,343', '4,192', '9,192', '2,800', '3,015', '3,015', '3,100', '3,415', '3,600', '3,570', '3,210', '1,900', '3,100', '2,747', '2,631', '2,419', '2,769', '3,163', '2,792', '3,018', '2,920', '3,541', '3,128', '2,020', '3,678', '3,522', '3,534', '3,078', '3,114', '8,206')
            """
        actual = self.util.get_the_insert_query(table_name, values_matix)
        self.assertEqual(actual.strip(), expected.strip())
