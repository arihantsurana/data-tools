from unittest import TestCase, mock

from hip_data_tools.google.common import GoogleApiConnectionSettings
from hip_data_tools.google.sheets.common import GoogleSheetConnectionManager
from hip_data_tools.google.sheets.sheets import SheetUtil


class TestS3Util(TestCase):
    @classmethod
    def setUpClass(cls):
        connection_manager = mock.Mock()
        cls.sheet_util = SheetUtil(conn_manager=connection_manager)

    @classmethod
    def tearDownClass(cls):
        return

    def integration_test_should__return_the_values_in_a_given_google_sheet__when_using_sheetUtil(self):
        sheet_util = SheetUtil(conn_manager=GoogleSheetConnectionManager(
            GoogleApiConnectionSettings(key_file_path='../resources/key-file.json')))
        workbook_name = 'Tradie Acquisition Targets'
        sheet_name = 'Sheet1'
        actual = sheet_util.get_value_matrix(workbook_name, sheet_name)
        expected = [['Jan-18', 'Feb-18', 'Mar-18', 'Apr-18', 'May-18', 'Jun-18', 'Jul-18', 'Aug-18', 'Sep-18', 'Oct-18',
                     'Nov-18', 'Dec-18', 'Jan-19', 'Feb-19', 'Mar-19', 'Apr-19', 'May-19', 'Jun-19', 'Jul-19', 'Aug-19',
                     'Sep-19', 'Oct-19', 'Nov-19', 'Dec-19', 'Jan-20', 'Feb-20', 'Mar-20', 'Apr-20', 'May-20',
                     'Jun-20'],
                    ['4,092', '3,192', '3,192', '2,800', '3,015', '3,015', '3,100', '3,415', '3,600', '3,570', '3,210',
                     '1,900', '3,100', '2,747', '2,631', '2,419', '2,769', '3,163', '2,792', '3,018', '2,920', '3,541',
                     '3,128', '2,020', '3,678', '3,522', '3,534', '3,078', '3,114', '3,206']]
        self.assertEqual(actual, expected)