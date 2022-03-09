# Copyright 2015 Rackspace
#
# Original from OpenCafe (https://github.com/openstack/opencafe)
#
# Changes copyright 2016 Intel
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from copy import deepcopy
import logging
import threading
from time import time

import requests
import six

from syntribos._i18n import _
import syntribos.checks.http as http_checks
import syntribos.signal
from syntribos.utils import string_utils

lock = threading.Lock()


def log_http_transaction(log, level=logging.DEBUG):
    """Decorator used for logging requests/response in clients.

    Takes a python Logger object and an optional logging level.
    """

    def _safe_decode(text, incoming='utf-8', errors='replace'):
        """Decodes incoming text/bytes using `incoming` if not already unicode.

        :param incoming: Text's current encoding
        :param errors: Errors handling policy. See here for valid
        values http://docs.python.org/2/library/codecs.html

        :returns: text or a unicode `incoming` encoded
        representation of it.
        """

        if isinstance(text, six.text_type):
            return text

        return text.decode(incoming, errors)

    def _decorator(func):
        """Accepts a function and returns wrapped version of that function."""
        def _wrapper(*args, **kwargs):
            """Logging wrapper for any method that returns a requests response.

            Logs requestslib response objects, and the args and kwargs
            sent to the request() method, to the provided log at the provided
            log level.
            """

            kwargs_copy = deepcopy(kwargs)
            if kwargs_copy.get("sanitize"):
                kwargs_copy = string_utils.sanitize_secrets(kwargs_copy)

            # Make the request and time its execution
            response = None
            no_resp_time = None
            signals = syntribos.signal.SignalHolder()
            try:
                start = time()
                response = func(*args, **kwargs)
            except requests.exceptions.RequestException as exc:
                signals.register(http_checks.check_fail(exc))
                log.log(level, _("A call to request() failed."))
                log.exception(exc)
                log.log(level, "=" * 80)
            except Exception as exc:
                log.critical('Call to Requests failed due to exception')
                log.exception(exc)
                signals.register(syntribos.signal.from_generic_exception(exc))
                raise exc

            if len(signals) > 0 and response is None:
                no_resp_time = time() - start
                log.log(level,
                        _(
                            'Request failed, elapsed time....: %.6f sec.\n'
                        ), no_resp_time)
                return (response, signals)

            # requests lib 1.0.0 renamed body to data in the request object
            request_body = ''
            if 'body' in dir(response.request):
                request_body = response.request.body
            elif 'data' in dir(response.request):
                request_body = response.request.data
            else:
                log.info("Unable to log request body, neither a 'data' nor a "
                         "'body' object could be found")

            # requests lib 1.0.4 removed params from response.request
            request_params = ''
            request_url = response.request.url
            if 'params' in dir(response.request):
                request_params = response.request.params
            elif '?' in request_url:
                request_url, request_params = request_url.split('?')

            response_content = response.content
            if kwargs_copy.get("sanitize"):
                response_content = string_utils.sanitize_secrets(
                    response_content)
                request_params = string_utils.sanitize_secrets(request_params)
                request_headers = string_utils.sanitize_secrets(
                    request_headers)
                request_body = string_utils.sanitize_secrets(request_body)
            return (response, signals)
        return _wrapper
    return _decorator
