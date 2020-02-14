"""
Module to deal with data transfer from Google sheets to Athena
"""
import logging as log
import re

from attr import dataclass

from hip_data_tools.aws.athena import AthenaUtil
from hip_data_tools.aws.common import AwsConnectionManager, AwsSecretsManager
from hip_data_tools.aws.common import AwsConnectionSettings
from hip_data_tools.aws.s3 import S3Util
from hip_data_tools.google.common import GoogleApiConnectionSettings
from hip_data_tools.google.sheets.common import GoogleSheetConnectionManager
from hip_data_tools.google.sheets.sheets import SheetUtil

DTYPE_GOOGLE_SHEET_TO_PARQUET_ATHENA = {
    "NUMBER": "DOUBLE",
    "STRING": "STRING",
    "BOOLEAN": "BOOLEAN"
}


@dataclass
class GoogleSheetsToAthenaSettings:
    """
    Google sheets to Athena ETL settings
    Args:
        workbook_name: the name of the workbook (eg: Tradie Acquisition Targets)
        sheet_name: name of the google sheet (eg: sheet1)
        row_range: range of rows (eg: '2:5')
        table_name: name of the athena table (eg: 'sheet_table')
        fields: list of sheet field names and types. Field names cannot contain hyphens('-')
            (eg: ['name:string','age:number','is_member:boolean'])
        use_derived_types: if this is false type of the fields are considered as strings irrespective of the provided
             field types (eg: True)
        s3_bucket: s3 bucket to store the files (eg: au-test-bucket)
        s3_dir: s3 directory to store the files (eg: sheets/new)
        skip_top_rows_count: number of top rows that need to be skipped (eg: 1)
        key_file_path: path of the google api key file (eg: path/key_file.json)
        database: name of the athena database (eg: dev)
        region: aws service region (eg: ap-southeast-2)
        profile: aws credentials profile (eg: default)
        secrets_manager: aws secret manager object
    """
    workbook_name: str
    sheet_name: str
    row_range: str
    table_name: str
    fields: list
    use_derived_types: bool
    s3_bucket: str
    s3_dir: str
    skip_top_rows_count: int
    key_file_path: str
    database: str
    region: str
    profile: str
    secrets_manager: AwsSecretsManager


class GoogleSheetToAthena:
    """
    Class to transfer data from google sheet to athena
    Args:
        settings (GoogleSheetsToAthenaSettings): the settings around the etl to be executed
    """

    def __init__(self, settings: GoogleSheetsToAthenaSettings):
        self.settings = settings
        self.keys_to_transfer = None

    def _get_sheets_util(self):
        return SheetUtil(conn_manager=GoogleSheetConnectionManager(
            GoogleApiConnectionSettings(key_file_path=self.settings.key_file_path)))

    def _get_athena_util(self):
        return AthenaUtil(database=self.settings.database, conn=AwsConnectionManager(
            AwsConnectionSettings(region=self.settings.region, secrets_manager=self.settings.secrets_manager,
                                  profile=self.settings.profile)), output_bucket=self.settings.s3_bucket)

    def _get_s3_util(self):
        return S3Util(
            bucket=self.settings.s3_bucket, conn=AwsConnectionManager(
                AwsConnectionSettings(region=self.settings.region, secrets_manager=self.settings.secrets_manager,
                                      profile=self.settings.profile)))

    def _simplified_dtype(self, data_type):
        """
        Return the athena base data type
        Args:
            data_type (string): data type
        :return:
        """
        return ((re.sub(r'\(.*\)', '', data_type)).split(" ", 1)[0]).upper()

    def _get_table_settings(self, table_name, fields, s3_bucket, s3_dir):
        """
        Get the table settings dictionary
        Args:
            table_name (string): name of the athena table
            fields (list): list of field names and types (eg: ['name:string','age:number','is_member:boolean'])
            s3_bucket (string): s3 bucket name
            s3_dir (string): s3 directory
        Returns: table settings dictionary

        """
        table_settings = {
            "table": table_name,
            "exists": True,
            "partitions": [],
            "columns": [],
            "storage_format_selector": "parquet",
            "s3_bucket": s3_bucket,
            "s3_dir": s3_dir,
            "encryption": False
        }
        columns = []
        if self.settings.use_derived_types:
            for field in fields:
                field_name_type = field.split(':')
                field_name = field_name_type[0]
                field_type = field_name_type[1]
                columns.append({"column": field_name,
                                "type": DTYPE_GOOGLE_SHEET_TO_PARQUET_ATHENA.get(
                                    str(self._simplified_dtype(field_type)),
                                    "STRING")})
        else:
            for field in fields:
                field_name = field.split(':')[0]
                columns.append({"column": field_name, "type": "string"})
        table_settings["columns"] = columns

        return table_settings

    def _get_the_insert_query(self, table_name, values_matrix):
        """
        Get the insert query for the athena table using the values matrix
        Args:
            table_name (string): name of the athena table
            values_matrix (array): values of the google sheet
        Returns: insert query for the athena table

        """
        if not values_matrix:
            return "INSERT INTO {table_name} VALUES ()".format(table_name=table_name)
        insert_query = "INSERT INTO {table_name} VALUES ".format(table_name=table_name)
        values = ""
        for value in values_matrix:
            values += "({}), ".format(', '.join(["'{}'".format(val) for val in value]))
        values = values[:-2]
        insert_query += values
        return insert_query

    def load_sheet_to_athena(self, overwrite_table=False):
        """
        Method to load google sheet to athena
        Args:
            overwrite_table (boolean): if this is true, it drops the existing athena table and clear the s3 location
        :return: None
        """
        sheet_util = self._get_sheets_util()
        athena_util = self._get_athena_util()
        s3_util = self._get_s3_util()
        if overwrite_table:
            athena_util.drop_table(self.settings.table_name)
            s3_util.delete_recursive(self.settings.s3_dir)
        values_matrix = sheet_util.get_value_matrix(workbook_name=self.settings.workbook_name,
                                                    sheet_name=self.settings.sheet_name,
                                                    row_range=self.settings.row_range,
                                                    skip_top_rows_count=self.settings.skip_top_rows_count)
        log.info("The value matrix:\n %s", values_matrix)
        table_settings = self._get_table_settings(table_name=self.settings.table_name,
                                                  fields=self.settings.fields,
                                                  s3_bucket=self.settings.s3_bucket,
                                                  s3_dir=self.settings.s3_dir)
        athena_util.create_table(table_settings)
        insert_query = self._get_the_insert_query(table_name=self.settings.table_name, values_matrix=values_matrix)
        log.info("The insert query:\n %s", insert_query)
        athena_util.run_query(query_string=insert_query)