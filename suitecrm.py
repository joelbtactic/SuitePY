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

import hashlib
import uuid
import json
from collections import OrderedDict
from urllib.parse import quote
from oauthlib.oauth2 import (
    BackendApplicationClient,
    TokenExpiredError,
    InvalidClientError,
)
from oauthlib.oauth2.rfc6749.errors import CustomOAuth2Error
from requests_oauthlib import OAuth2Session
import requests
from .suite_exceptions import *
from .bean import Bean
from .bean_exceptions import *
from .config import Config
from .singleton import Singleton
from .filter import *

class SuiteCRM(Singleton):
    """
    This class contains methods to interact with a SuiteCRM instance.
    """

    conf = Config()

    # The follwing URLs are for the SuiteCRM 8.X versions
    TOKEN_URL = '/legacy/Api/access_token'
    MODULE_URL = '/legacy/Api/V8/module'

    # The following URLs are for the SuiteCRM 7.X versions
    # TOKEN_URL = '/Api/access_token'
    # MODULE_URL = '/Api/V8/module'

    def get_token(self):
        return self._access_token

    def __init__(self):
        self._access_token = ''
        self._headers = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 '
            '(KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36'
        )
        self._login()

    def _call(self, the_method, parameters, url, data, custom_parameters):
        try:
            if parameters == '':
                data = the_method(url)
            else:
                data = the_method(url, data=data)
        except TokenExpiredError:
            self._refresh_token()
            if parameters == '':
                data = the_method(url)
            else:
                data = the_method(url, data=data)
        return data

    def _request(self, url: str, method, parameters='', custom_parameters=''):
        """
        Makes a request to the given url with a specific method and data. If the request fails because the token expired
        the session will re-authenticate and attempt the request again with a new token.
        :param url: (string) The url
        :param method: (string) Get, Post, Patch, Delete
        :param parameters: (dictionary) Data to be posted
        :param custom_parameters: parameters that are not sent in the calls and not indicated in the url, is used for caching.
        :return: (dictionary) Data
        """
        url = quote(url, safe='/:?=&')
        data = json.dumps({"data": parameters})
        try:
            the_method = getattr(self.OAuth2Session, method)
        except AttributeError:
            return
        data = self._call(the_method, parameters, url, data, custom_parameters)

        if data.status_code == 401:
            data = self._revoke_token(the_method, parameters, url, data)

        if data.status_code == 400:
            exit('400 (BAD REQUEST)')

        # Database Failure
        # SuiteCRM does not allow to query by a custom field see README, #Limitations
        if data.status_code == 400 and 'Database failure.' in data.content.decode():
            raise Exception(data.content.decode())

        return json.loads(data.content)
            
    def _revoke_token(self, the_method, parameters, url, data):
        attempts = 0
        while attempts < 1:
            self._refresh_token()
            self._call(the_method, parameters, url, data)
            attempts += 1
        if data.status_code == 401:
            exit(
                '401 (Unauthorized) client id/secret has been revoked, new token was attempted and failed.'
            )

        return data

    def _login(self):
        """
        Checks to see if a Oauth2 Session exists,
        if not builds a session and retrieves the token from the config file,
        if no token in config file, fetch a new one.
        :return: None
        """
        # Does session exist?
        if not hasattr(self, 'OAuth2Session'):
            client = BackendApplicationClient(client_id=self.conf.client_id)
            self.OAuth2Session = OAuth2Session(
                client=client, client_id=self.conf.client_id
            )
            self.OAuth2Session.headers.update(
                {"User-Agent": self._headers, 'Content-Type': 'application/json'}
            )
            if self._access_token == '':
                self._refresh_token()
            else:
                self.OAuth2Session.token = self._access_token
        else:
            self._refresh_token()

    def _refresh_token(self) -> None:
        """
        Fetch a new token from from token access url, specified in config file.
        :return: None
        """
        try:
            self.OAuth2Session.fetch_token(
                token_url=self.conf.url + self.TOKEN_URL,
                client_id=self.conf.client_id,
                client_secret=self.conf.client_secret,
                verify=self.conf.verify_ssl,
            )

        except InvalidClientError:
            exit('401 (Unauthorized) - client id/secret')
        except CustomOAuth2Error:
            exit('401 (Unauthorized) - client id')
        # Update configuration file with new token'
        self._access_token = str(self.OAuth2Session.token)

    @staticmethod
    def _get_bean_failed(result):
        try:
            return result['entry_list'][0]['name_value_list'][0]['name'] == 'warning'
        except Exception:
            return False

    def get_available_modules(self):
        """
        Returns all the available modules
        """
        url = '/legacy/Api/V8/meta/modules'
        response = self._request(f'{self.conf.url}{url}', 'get')
        return self._format_get_modules_response(response)

    def _format_get_modules_response(self, response):
        lst = ['AM_', 'AOS_', 'AOR_', 'AOK_', 'FP_']
        list_response = []
        for key, values in response['data']['attributes'].items():
            values['module_key'] = key
            for pattern in lst:
                if pattern in key:
                    key = key.replace(pattern, '')
            label = key.replace('_', ' ')
            values['label'] = label[0].upper() + label[1:]
            values['module_label'] = values.pop('label')
            list_response.append(values)
        return {"modules": list_response}

    def get_module_fields(self, module_name, fields = []):
        url = f'/legacy/Api/V8/meta/fields/{module_name}'
        response = self._request(
            f'{self.conf.url}{url}', 'get', custom_parameters=fields
        )['data']
        return self._format_get_module_fields_response(response, fields)

    def _format_get_module_fields_response(self, response, fields):
        response['module_fields'] = response.pop('attributes')
        all_fields = response['module_fields'].keys()
        rem_fields = set(all_fields).difference(fields)
        if len(fields) > 0:
            for field in rem_fields:
                response['module_fields'].pop(field)

        return response

    def get_bean(self, module_name, id, fields=None, link_name_to_fields_array=''):
        """
        Gets records given a specific id or filters, can be sorted only once, and the fields returned for each record
        can be specified.
        :param module_name: The name of the module
        :param id: The id of the record
        :param fields: (list) A list of fields you want to be returned from each record.
        :param link_name_to_fields_array: a list of link_names and for each link_name.
        :return: (list) A list of dictionaries, where each dictionary is a record.
        """
        # Fields Constructor
        if fields:
            fields = f'?fields[{module_name}]=' + ','.join(fields)
            url = f'/{module_name}/{id}{fields}'
        else:
            url = f'/{module_name}/{id}'

        list_relationship = None
        # Execute
        response = self._request(f'{self.conf.url}{self.MODULE_URL}{url}', 'get')[
            'data'
        ]

        if link_name_to_fields_array != '':
            list_relationship = self._get_bean_relationships(
                link_name_to_fields_array, module_name, id
            )
        bean = Bean(
            module_name, response['attributes'], list_relationship, response['id']
        )
        return bean

    def _get_bean_relationships(self, relationships, module_name, id):
        list_module_relationships = []
        list_relationships = {}
        for items in relationships:
            list_module_relationships.append(items['name'])

        for module_relation in list_module_relationships:
            data = self.get_relationships(
                module_name, id, module_relation, bean_relationship=True
            )
            if data['data'] != []:
                list_relationships[str(data['data'][0]['type'])] = data['data']

        return list_relationships

    def get_bean_list(
        self,
        module_name,
        fields=None,
        filter=None,
        max_results='',
        offset=1,
        order_by=None,
    ):
        connectors = ["?", "&"]
        connectors_idx = 0
        url = f'{self.conf.url}{self.MODULE_URL}/{module_name}'

        # Fields Constructor
        if fields:
            url += f'{connectors[connectors_idx]}fields[{module_name}]=' + ','.join(fields)
            connectors_idx = 1

        if offset:
            url += '{0}page[number]={1}'.format(connectors[connectors_idx], offset)
            connectors_idx = 1

        if max_results:
            url += '{0}page[size]={1}'.format(connectors[connectors_idx], max_results)

        if order_by:
            url += f'{connectors[connectors_idx]}sort=-{order_by}'
            connectors_idx = 1

        if filter:
            filter = from_legacy_query(filter)
            url += '{0}{1}'.format(
                connectors[connectors_idx], filter.to_filter_string()
            )
            connectors_idx = 1

        response = self._request(f'{url}', 'get')
        next_page = response.get('links', {}).get('next')
        prev_page = response.get('links', {}).get('prev')
        bean_list = []
        for value in response['data']:
            bean_list.append(
                Bean(
                    module=value['type'],
                    name_value_list=value['attributes'],
                    id=value['id'],
                )
            )
        return {
            "entry_list": bean_list,
            "result_count": len(bean_list),
            "previous_offset": offset - 1 if prev_page != None else None,
            "current_offset": offset,
            "next_offset": offset + 1 if next_page != None else None,
            "current_limit": max_results,
        }

    def get_relationships(
        self,
        module_name,
        id: str,
        related_module_name: str,
        only_relationship_fields: bool = False,
        link_name_to_fields_array='',
        limit='',
        offset='',
        order_by='',
        bean_relationship: bool = False,
        filter='',
        order=None,
    ) -> dict:
        """
        """
        connectors = ["?", "&"]
        sort_order = {"desc": "-", None: ""}
        connectors_idx = 0

        url = f'/{module_name}/{id}/relationships/{related_module_name.lower()}'

        if order_by:
            url += '{0}sort={1}{2}'.format(
                connectors[connectors_idx], sort_order[order], order_by
            )
            connectors_idx = 1

        if filter:
            filter = from_legacy_query(filter)
            url += '{0}{1}'.format(
                connectors[connectors_idx], filter.to_filter_string()
            )
            connectors_idx = 1

        if offset:
            url += '{0}page[number]={1}'.format(connectors[connectors_idx], offset)
            connectors_idx = 1

        if limit:
            url += '{0}page[size]={1}'.format(connectors[connectors_idx], limit)

        response = self._request(f'{self.conf.url}{self.MODULE_URL}{url}', 'get')
        next_page = response.get("links", {}).get("next")
        prev_page = response.get("links", {}).get("prev")

        if bean_relationship:
            return response

        bean_list = []
        if only_relationship_fields:
            for value in response['data']:
                bean_list.append(
                    Bean(
                        module=value['type'],
                        name_value_list=value['attributes'],
                        id=value['id'],
                    )
                )
        else:
            for value in response['data']:
                bean_list.append(
                    self.get_bean(
                        value['type'],
                        value['id'],
                        link_name_to_fields_array=link_name_to_fields_array,
                    )
                )
        return {
            "entry_list": bean_list,
            "result_count": len(bean_list),
            "previous_offset": offset - 1 if prev_page != None else None,
            "current_offset": offset,
            "next_offset": offset + 1 if next_page != None else None,
            "current_limit": limit,
        }

    def save_bean(self, bean: Bean, update: bool = False):
        module = bean.module
        attributes = bean.get_bean_fields()
        if update:
            data = {'type': module, 'id': bean['id'], 'attributes': attributes}
            response = self._request(f"{self.conf.url}{self.MODULE_URL}", "patch", data)
        else:
            data = {'type': module, 'attributes': attributes}
            response = self._request(f'{self.conf.url}{self.MODULE_URL}', 'post', data)
            bean['id'] = response['data']['id']
        return response

    def set_relationship(
        self, module_name, module_id, related_names, related_ids, delete=False
    ):
        """
        Creates a relationship between 2 records.
        :param module_name: name of the module
        :param module_id: (string) id of the current module record.
        :param related_names: the modules names of the records you want to create a relationships,
               ie. Contacts.
        :param related_ids: ids of the records inside of the other module.
        :return: (list) A list with the responses of the relationships created/deleted.
        """
        if delete:
            return self._delete_relationship(
                module_name, module_id, related_names, related_ids
            )
        return self._create_relationship(
            module_name, module_id, related_names, related_ids
        )

    def _create_relationship(
        self, module_name, module_id, related_module_name, related_ids
    ):

        # Post
        response = []
        url = f'/{module_name}/{module_id}/relationships'
        for related_id in related_ids:
            data = {'type': related_module_name, 'id': related_id}
            response.append(
                self._request(f'{self.conf.url}{self.MODULE_URL}{url}', 'post', data)
            )
        return response

    def _delete_relationship(
        self, module_name, module_id, related_module_names, related_ids
    ):
        response = []
        for related_module_name, related_id in zip(related_module_names, related_ids):
            url = f'/{module_name}/{module_id}/relationships/{related_module_name.lower()}/{related_id}'
            response.append(
                self._request(f'{self.conf.url}{self.MODULE_URL}{url}', 'delete')
            )
        return response

    def get_note_attachment(self, note_id):
        """
        Retrieve an attachment from a note.

        :param str note_id: ID of the appropriate Note.
        :return: the requested attachment.
        :rtype: dict[str, object]
        """
        url = f'/legacy/Api/V8/custom/getNoteAttach/{note_id}'

        response = self._request(f'{self.conf.url}{url}', 'get')
        return response

    def get_pdf_template(self, template_id, bean_module, bean_id):
        """
        Retrieve PDF Template for a given module record.

        :param str template_id: template ID used to generate PDF.
        :param str bean_module: module name of the bean that will be used to populate PDF.
        :param str bean_id: ID of the bean record.
        :return: the generated PDF.
        :rtype: dict[str, str]
        """

        url = f'/legacy/Api/V8/custom/getPdfTemplate/{bean_module}/{bean_id}/{template_id}'

        response = self._request(f'{self.conf.url}{url}', 'get')
        return response
