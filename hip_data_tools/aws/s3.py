"""
Utility to connect to, and interact with the s3 file storage system
"""
import json
import logging as log
import os
import uuid
from multiprocessing.pool import Pool
from pathlib import Path
from typing import List, Any

import arrow
import pandas as pd
from joblib import load, dump
from pandas import DataFrame

from hip_data_tools.aws.common import AwsUtil, AwsConnectionManager, AwsConnectionSettings
from hip_data_tools.common import _generate_random_file_name


class S3Util(AwsUtil):
    """
    Utility class for connecting to s3 and manipulate data in a pythonic way
    Args:
        conn (AwsConnection): AwsConnection object or a boto.Session object
        bucket (string): S3 bucket name where these operations will take place
    """

    def __init__(self, conn: AwsConnectionManager, bucket: str):
        super().__init__(conn, "s3")
        self.bucket = bucket

    def download_file(self, local_file_path: str, key: str) -> None:
        """
        Downloads a file from a path on s3 to a local path on disk
        Args:
            local_file_path (str): Absolute path on s3.
            key (str): Absolute path to save file to local.
        Returns: None
        """
        self.get_client().download_file(self.bucket, key, local_file_path)

    def upload_file(self, local_file_path: str, key: str, remove_local: bool = True) -> None:
        """
        Uploads a file from local to s3
        Args:
            local_file_path (str): Absolute local path to the file to upload
            key (str): Absolute path within the s3 buck to upload the file
            remove_local (bool): remove file from local fs after transfer
        Returns: None
        """
        self.get_client().upload_file(local_file_path, self.bucket, key)
        if remove_local:
            os.remove(local_file_path)

    def download_object_and_deserialise(self, key: str, local_file_path: str = None):
        """
        Download a serialised object from S3 and deserialize
        Args:
            key (str): Absolute path on s3 to the file
            local_file_path (str): The deserialized object
        Returns: object
        """
        if local_file_path is None:
            local_file_path = "/tmp/tmp_file{}".format(str(uuid.uuid4()))

        self.download_file(key=key, local_file_path=local_file_path)
        return load(local_file_path)

    def serialise_and_upload_object(self, obj: Any, key: str) -> None:
        """
        Serialise any object to disk, and then upload to S3
        Args:
            obj (Any): Any serialisable object
            key (str): The absolute path on s3 to upload the file to
        Returns: None
        """

        random_tmp_file_nm = _generate_random_file_name()
        dump(obj, random_tmp_file_nm)
        self.upload_file(local_file_path=random_tmp_file_nm, key=key)

    def create_bucket(self) -> None:
        """
        Creates the s3 bucket
        Returns: None
        """
        self.get_resource().create_bucket(Bucket=self.bucket)

    def upload_dataframe_as_parquet(self,
                                    dataframe: DataFrame,
                                    key: str,
                                    file_name: str = "data") -> None:
        """
        Exports a datafame to a parquet file on s3
        Args:
            dataframe (DataFrame): dataframe to export
            key (str): The absolute path on s3 to upload the file to
            file_name (str): the name of the file at destination
        Returns: None
        """
        destination = "s3://{}/{}/{}.parquet".format(self.bucket, key, file_name)
        dataframe.to_parquet(fname=destination)

    def download_parquet_as_dataframe(self,
                                      key: str,
                                      engine: str = 'auto',
                                      columns: List[str] = None,
                                      **kwargs) -> DataFrame:
        """
        Exports a datafame to a parquet file on s3
        Args:
            key (str): The absolute path on s3 to upload the file to
            engine (str): parquet engine
            columns (lis[str]): list of columns default None to extrapolate from dataframe
        Returns: DataFrame
        """
        random_tmp_file_nm = _generate_random_file_name()
        self.download_file(random_tmp_file_nm, key)
        return pd.read_parquet(random_tmp_file_nm, engine=engine, columns=columns, **kwargs)

    def read_lines_as_list(self, key_prefix: str) -> List[str]:
        """
        Read lines from s3 files
        Args:
            key_prefix (str): the key prefix under which all files will be read
        Returns: list[str] lines read from all files
        """
        s3 = self.get_resource()
        bucket = s3.Bucket(name=self.bucket)
        lines = []
        log.info("reading files from s3://%s/%s ", self.bucket, key_prefix)
        file_metadata = bucket.objects.filter(Prefix=key_prefix)
        for file in file_metadata:
            obj = s3.Object(self.bucket, file.key)
            data = obj.get()["Body"].read().decode("utf-8")
            lines.append(data.splitlines())
        # Flatten the list of lists
        flat_lines = [item for sublist in lines for item in sublist]
        log.info("Read %d lines from %d s3 files", len(flat_lines), len(lines))
        return flat_lines

    def delete_recursive(self, key_prefix: str) -> None:
        """
        Recursively delete all keys with given prefix from the named bucket
        Args:
            key_prefix (str): Key prefix under which all files will be deleted
        Returns: NA
        """
        log.info("Recursively deleting s3://%s/%s", self.bucket, key_prefix)
        response = self.get_resource().Bucket(self.bucket).objects.filter(
            Prefix=key_prefix).delete()
        log.info(response)

    def get_keys(self, key_prefix: str) -> List[str]:
        """
        returns a list of all objects unser a given key prefix
        Args:
            key_prefix (str): Key Prefix under which all objects are to be listed
        Returns: list[str]
        """
        continuation_token = None
        keys = []
        while True:
            result = self._list_object_page(key_prefix, continuation_token)

            keys = keys + [content.get('Key', None) for content in result.get('Contents', [])]
            if 'NextContinuationToken' not in result:
                break
            continuation_token = result['NextContinuationToken']
        return keys

    def _list_object_page(self, key_prefix: str, continuation_token: str):
        if continuation_token is None:
            return self.get_client().list_objects_v2(
                Bucket=self.bucket,
                Prefix=key_prefix,
            )
        return self.get_client().list_objects_v2(
            Bucket=self.bucket,
            Prefix=key_prefix,
            ContinuationToken=continuation_token,
        )

    def upload_directory(self,
                         source_directory: str,
                         extension: str,
                         target_key: str,
                         overwrite: bool = True,
                         rename: bool = True) -> None:
        """
        Upload a local file directory to s3
        Args:
            source_directory (str): Local source directory's absolute path.
            extension (str): the file extension of files in that directory to be uploaded.
            target_key (str): Target location on the s3 bucket for files to be uploaded.
            overwrite (bool): overwrites files on s3 if set to true.
            rename (bool): renames the file when uploading to s3 if set to true.
        Returns: None
        """
        if overwrite:
            log.info("Cleaning existing files on s3")
            self.delete_recursive(f"{target_key}/")
        log.info("searching for files to upload in %s", source_directory)
        path_list = Path(source_directory).glob(f'**/*.{extension}')
        itr = 0
        upload_data = []
        for path in path_list:
            path_in_str = str(path)
            filename = os.path.basename(path_in_str)
            if rename:
                filename = f"file-{str(uuid.uuid4())}.{extension}"
            destination_key = f"{target_key}/{filename}"
            itr = itr + 1
            upload_data += [(self.conn.settings, path_in_str, self.bucket, destination_key)]
        pool_size = min(16, max(1, int(len(upload_data) / 3)))  # limit pool size between 1 and 16
        log.debug("uploading with a multiprocessing pool of %s processes", pool_size)

        Pool(pool_size).starmap(_multi_process_upload_file, upload_data)
        log.info("Upload of directory complete at s3://%s/%s", self.bucket, target_key)

    def delete_recursive_match_suffix(self, key_prefix: str, suffix: str) -> None:
        """
        Recursively delete all keys with given key prefix and suffix from the bucket
        Args:
            key_prefix (str): Key prefix under which all files will be deleted.
            suffix (str): suffix of the subset of files in the given prefix directory to be deleted
        Returns: None
        """
        if not key_prefix:
            raise ValueError("key_prefix must not be empty")
        if not suffix:
            raise ValueError("suffix must not be empty")
        s3 = self.get_resource()
        for obj in s3.Bucket(self.bucket).objects.filter(Prefix=key_prefix):
            if obj.key.endswith(suffix):
                log.info("deleting s3://%s/%s", self.bucket, obj.key)
                response = obj.delete()
                log.info("Response: %s ", response)

    def download_directory(self, source_key: str, file_suffix: str, local_directory: str) -> None:
        """
        Download an entire directory from s3 onto local file system
        Args:
            source_key (str): key prefix of the directory to be downloaded from s3
            file_suffix (str): suffix to filter a subset under the source_key to be downloaded
            local_directory (str): local absolute path to store all the files
        Returns: None
        """
        s3 = self.get_resource()
        log.info("Downloading s3://%s/%s to %s", self.bucket, source_key, local_directory)
        for obj in s3.Bucket(self.bucket).objects.filter(Prefix=source_key):
            key_path = obj.key.split("/")
            if obj.key.endswith(file_suffix):
                filename = f"{local_directory}/{key_path[-1]}"
                self.download_file(
                    local_file_path=filename,
                    key=obj.key)

    def upload_json(self, key: str, json_list: List[dict]) -> None:
        """
        Save the json/dict data structure onto s3 as a file without using temporary local files
        Args:
            key: target key of the file on s3
            json_list: a list of dictionaries that are saved as newline json in a file
        Returns: None
        """
        s3 = self.get_resource()
        s3.Object(self.bucket, key).put(
            Body=(bytes(json.dumps(json_list, indent=2).encode('UTF-8')))
        )

    def download_json(self, key: str) -> dict:
        """
        Read a file in json format from s3
        Args:
            key: location of the file to read
        Returns: dict
        """
        s3 = self.get_resource()
        json_content = json.loads(
            s3.Object(self.bucket, key).get()['Body'].read().decode('utf-8')
        )
        return json_content

    def downlaod_strings(self, key: str) -> List[str]:
        """
        Read lines from s3 files
        Args:
            key: the key for the file which contains strings
        Returns: List[str]
        """
        s3 = self.get_resource()
        obj = s3.Object(self.bucket, key)
        data = obj.get()['Body'].read().decode('utf-8')
        lines = data.splitlines()
        return lines

    def get_keys_modified_in_range(self,
                                   key_prefix: str,
                                   start_date: arrow,
                                   end_date: arrow) -> List[str]:
        """
        Sense if there were any files changed or added in the given time period under the given key
        prefix and return a list of keys
        Args:
            key_prefix: the key prefix under which all files will be sensed
            start_date: start of the duration in which the s3 objects were modified
            end_date: end of the duration in which the s3 objects were modified
        Returns: List[str]
        """
        log.info("sensing files from s3://%s/%s \n between %s to %s", self.bucket, key_prefix,
                 start_date, end_date)
        metadata = self.get_object_metadata(key_prefix)
        lines = []
        for file in metadata:
            if start_date < arrow.get(file.last_modified) <= end_date:
                lines += [file.key]
        log.info("found %s s3 files changed", len(lines))
        return lines

    def get_object_metadata(self, key_prefix: str) -> List:
        """
        Get metadata for all objects under a key prefix
        Args:
            key_prefix: the key prefix under which all files will be sensed
        Returns: List[metadata]
        """
        s3 = self.get_resource()
        bucket = s3.Bucket(name=self.bucket)
        metadata = bucket.objects.filter(Prefix=key_prefix)
        return metadata

    def upload_binary_stream(self, stream: bytes, key: str) -> None:
        """
        Upload a binary stream of data as an s3 object's body
        Args:
            stream: the stream of bytes tobe uploaded
            key: s3 key at which thios stream is to be uploaded
        Returns: None
        """
        s3 = self.get_resource()
        obj = s3.Object(self.bucket, key)
        obj.put(Body=stream)

    def move_recursive(self,
                       source_dir: str,
                       destination_dir: str,
                       delete_after_copy: bool = True) -> None:
        """
        recursively move files on s3 to a new location on the same bucket
        Args:
            source_dir: Source key prefix representing the directory to move
            destination_dir: destination key prefix
            delete_after_copy: option to remove the files from source after successful copy
        Returns: None
        """
        s3 = self.get_resource()
        bucket = s3.Bucket(self.bucket)
        for obj in bucket.objects.filter(Prefix=source_dir):
            # replace the prefix
            new_key = destination_dir + obj.key[len(source_dir):]
            log.info("Moving s3 object from : \n%s \nto: \n%s", obj.key, new_key)
            new_obj = bucket.Object(new_key)
            new_obj.copy({'Bucket': self.bucket, 'Key': obj.key})
        if delete_after_copy:
            self.delete_recursive(source_dir)

    def rename_file(self, key: str, new_file_name: str) -> None:
        """
        Rename a file on s3
        Args:
            key: Current key of the file
            new_file_name: new file name to be cjhanged for the file
        Returns: None
        """
        s3 = self.get_resource()
        full_new_file_path = key.rpartition('/')[0] + '/' + new_file_name
        log.info("Renaming source: %s to %s", key, full_new_file_path)
        s3.Object(self.bucket, full_new_file_path).copy_from(
            CopySource={'Bucket': self.bucket, 'Key': key})
        s3.Object(self.bucket, key).delete()

    def download_strings_from_directory(self, key_prefix: str) -> List[str]:
        """
        Read lines from s3 files
        Args:
            key_prefix: the key prefix under which all files will be read
        Returns: List[str]
        """
        s3 = self.get_resource()
        bucket = s3.Bucket(name=self.bucket)
        lines = []
        log.info("reading files from s3://%s/%s", self.bucket, key_prefix)
        file_metadata = bucket.objects.filter(Prefix=key_prefix)
        for file in file_metadata:
            obj = s3.Object(self.bucket, file.key)
            data = obj.get()['Body'].read().decode('utf-8')
            lines.append(data.splitlines())
        # Flatten the list of lists
        flat_lines = [item for sublist in lines for item in sublist]
        log.info("read %s lines from %s s3 files", len(flat_lines), len(lines))
        return flat_lines


def _multi_process_upload_file(settings: AwsConnectionSettings, filename: str, bucket: str,
                               key: str) -> None:
    """
    A standalone copy of the method making it simple to pickle in a multi processing pool
    Args:
        conn: the s3 connection manager to use for upload
        filename: local file name of the file to be uploaded.
        bucket: the s3 bucket to upload file to .
        key: the s3 key to use whiole uploading the file
    Returns: None
    """
    log.info("Uploading File %s to s3://%s/%s", filename, bucket, key)
    S3Util(
        conn=AwsConnectionManager(settings),
        bucket=bucket
    ).upload_file(local_file_path=filename, key=key)
