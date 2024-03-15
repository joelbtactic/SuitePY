#######################################################################
# Suite PY is a simple Python client for SuiteCRM API.

# Copyright (C) 2017-2018 BTACTIC, SCCL
# Copyright (C) 2017-2018 Marc Sanchez Fauste

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.

# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#######################################################################

import json
import time
from .suitecrm import SuiteCRM
from collections import OrderedDict


class SuiteCRMCached(SuiteCRM):
    """
    This class allows you to make cached calls to SuiteCRM.
    When making a request, first look if its in the cache and,
    if is not on the cache, make the request to SuiteCRM, save it
    in the cache and finally return the result of the request.

    The cache has a limit of cached requests, when this limit is reached,
    the request that has not been accessed for a longer time is eliminated.

    This class allows you to make the same calls as the SuiteCRM class.
    Its the responsibility of the programmer to determine when to
    use SuiteCRM or SuiteCRMCached, taking into account that the
    information returned by SuiteCRMCached may not be updated with
    the existing information on the SuiteCRM instance.
    """

    _cache = {}
    _cache_accessed = {}
    _max_cached_requests = 100

    def _login(self):
        """
        Checks to see if a Oauth2 Session exists,
        if not builds a session and retrieves the token from the config file,
        if no token in config file, fetch a new one.
        :return: None
        """
        return super(SuiteCRMCached, self)._login()

    def _call(self, method, parameters, url, data, custom_parameters=''):
        cached_call = self._get_cached_call(method, url, custom_parameters)
        if cached_call:
            return cached_call
        else:
            response = super(SuiteCRMCached, self)._call(method, parameters, url, data, custom_parameters)
            self._add_call_to_cache(method, url, custom_parameters, response)
            return response

    @staticmethod
    def _get_time():
        return time.time()

    def _get_oldest_accessed_cache_key(self):
        try:
            oldest_accessed = None
            for key, timestamp in self._cache_accessed.items():
                if oldest_accessed and oldest_accessed[1] > timestamp:
                    oldest_accessed = (key, timestamp)
                else:
                    oldest_accessed = (key, timestamp)
            return oldest_accessed[0]
        except Exception:
            return None

    def _remove_oldest_cached_requests(self):
        if len(self._cache) > self._max_cached_requests:
            oldest_accessed = self._get_oldest_accessed_cache_key()
            if oldest_accessed:
                del self._cache[oldest_accessed]
                del self._cache_accessed[oldest_accessed]

    def _add_call_to_cache(self, method, url, custom_parameters, response):
        try:
            key = (method, json.dumps(custom_parameters), url)
            self._cache[key] = response
            self._cache_accessed[key] = self._get_time()
            self._remove_oldest_cached_requests()
            return True
        except Exception:
            return False

    def _get_cached_call(self, method, url, custom_parameters):
        try:
            key = (method, json.dumps(custom_parameters), url)
            cached_response = self._cache[key]
            self._cache_accessed[key] = self._get_time()
            return cached_response
        except Exception:
            return None

    def clear_cache(self):
        """
        This method clears all the information stored on the internal cache.
        """
        self._cache.clear()
        self._cache_accessed.clear()

    def get_number_of_cached_calls(self):
        """
        Get the number of cached calls.

        :return: number of cached calls.
        :rtype: int
        """
        return len(self._cache)
