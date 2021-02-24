import os
import json
import re
from syntribos.constants import COMPRESSION_ENABLED, PAYLOADS_PATH
import sys
import unittest
from multiprocessing.dummy import Pool as ThreadPool
import uuid
from xml.etree import ElementTree

import yaml

from syntribos import tests
import syntribos.tests as tests
import syntribos.tests.base
from syntribos.runner import Runner
from syntribos.clients.http.parser import RequestCreator, RequestObject

class Scanner():
    def __init__(
        self,
        method,
        url,
        headers=None,
        params=None,
        data=None,
        payload_path="",
        compression_enabled=True
    ) -> None:
        COMPRESSION_ENABLED = compression_enabled
        PAYLOADS_PATH = payload_path
        self.request = self.create_request(
            method,
            url,
            headers,
            params,
            data,
        )
        decorator = unittest.runner._WritelnDecorator(sys.stdout)
        self.result = syntribos.result.IssueTestResult(decorator, True, verbosity=1)
        Runner.load_modules(tests)
        self.all_tests = sorted((syntribos.tests.base.test_table).items())
    
    def create_request(self, method, url, headers, params, data):
        action_field = str(uuid.uuid4()).replace("-", "")
        content_type = ''
        if headers:
            for h in headers:
                if h.upper() == 'CONTENT-TYPE':
                    content_type = headers[h]
                    break
        data, data_type = self.parse_data(data, content_type)
        return RequestObject(
            method=method,
            url=url,
            headers=headers if headers else {},
            params=params if params else {},
            data=data,
            action_field=action_field,
            data_type=data_type
        )
    
    def parse_data(self, data, content_type=""):
        postdat_regex = r"([\w%]+=[\w%]+&?)+"
        data_type = "text"
        if not data:
            return '', None
        try:
            data = json.loads(data)
            # TODO(cneill): Make this less hacky
            if isinstance(data, list):
                data = json.dumps(data)
            if isinstance(data, dict):
                return RequestCreator._replace_dict_variables(data), 'json'
            else:
                return RequestCreator._replace_str_variables(data), 'str'
        except Exception:
            raise
        except (TypeError, ValueError):
            if 'json' in content_type:
                msg = ("The Content-Type header provided is %s but "
                       "cannot parse the request body as json" %
                       content_type)
                raise Exception(msg)
            try:
                data = ElementTree.fromstring(data)
                data_type = 'xml'
            except Exception:
                if 'xml' in content_type:
                    msg = ("The Content-Type header provided is %s "
                           "but cannot parse the request body as xml"
                           % content_type)
                    raise Exception(msg)
                try:
                    data = yaml.safe_load(data)
                    data_type = 'yaml'
                except yaml.YAMLError:
                    if 'yaml' in content_type:
                        msg = ("The Content-Type header provided is %s"
                               "but cannot parse the request body as"
                               "yaml"
                               % content_type)
                        raise Exception(msg)
                    if not re.match(postdat_regex, data):
                        raise TypeError("Make sure that your request body is"
                                          "valid JSON, XML, or YAML data - be "
                                          "sure to check for typos.")
        except Exception:
            raise
        return data, data_type
        


    def run(self, test):
        pool = ThreadPool(16)
        list_of_tests = [x for x in self.all_tests if test in x[0]]
        for test_name, test_class in list_of_tests:
            test_class.set_init_request(self.request)
            test_class.send_init_request(None, None, None)
            

            test_cases = list(test_class.get_test_cases_from_req_obj(
                    self.request
                )
            )
            pool.map(lambda t: Runner.run_test_on_result(t, self.result), test_cases)


