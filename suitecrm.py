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
from oauthlib.oauth2 import BackendApplicationClient, TokenExpiredError, InvalidClientError
from oauthlib.oauth2.rfc6749.errors import CustomOAuth2Error
from requests_oauthlib import OAuth2Session
import requests
from suite_exceptions import *
from bean import Bean
from bean_exceptions import *
from config import Config
from singleton import Singleton

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
        self._headers = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' \
                        '(KHTML, like Gecko) Chrome/97.0.4692.99 Safari/537.36'
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

    def _request(self, url: str, method, parameters=''):
        """
        Makes a request to the given url with a specific method and data. If the request fails because the token expired
        the session will re-authenticate and attempt the request again with a new token.
        :param url: (string) The url
        :param method: (string) Get, Post, Patch, Delete
        :param parameters: (dictionary) Data to be posted
        :return: (dictionary) Data
        """
        url = quote(url, safe='/:?=&')
        data = json.dumps({"data": parameters})
        try:
            the_method = getattr(self.OAuth2Session, method)
        except AttributeError:
            return
        data = self._call(the_method, parameters, url, data)

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
            exit('401 (Unauthorized) client id/secret has been revoked, new token was attempted and failed.')
        
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
            self.OAuth2Session = OAuth2Session(client=client,
                                               client_id=self.conf.client_id)
            self.OAuth2Session.headers.update({"User-Agent": self._headers,
                                               'Content-Type': 'application/json'})
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
            self.OAuth2Session.fetch_token(token_url=self.conf.url + self.TOKEN_URL,
                                           client_id=self.conf.client_id,
                                           client_secret=self.conf.client_secret)
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

    def get_modules(self):
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
        return list_response

    def get_module_fields_v8(self, module_name, fields = []):
        url = f'/legacy/Api/V8/meta/fields/{module_name}'
        response = self._request(f'{self.conf.url}{url}', 'get', custom_parameters=fields)['data']
        return self._format_get_module_fields_response(response, fields)

    def _format_get_module_fields_response(self, response, fields):
        response['module_fields'] = response.pop('attributes')
        all_fields = response['module_fields'].keys()
        rem_fields = set(all_fields).difference(fields)
        if len(fields) > 0:
            for field in rem_fields:
                response['module_fields'].pop(field)

        for key, values in response['module_fields'].items():
            values['label'] = key
        return response
        
    def get_bean_v8(self, module_name, id, fields=None, link_name_to_fields_array=''):
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
        response =  self._request(f'{self.conf.url}{self.MODULE_URL}{url}', 'get')['data']
        if link_name_to_fields_array != '':
            list_relationship = self._get_bean_relationships(link_name_to_fields_array, module_name, id)
        bean = Bean(module_name,response['attributes'], list_relationship)
        # print(response)
        return bean

    def _get_bean_relationships(self, relationships, module_name, id):
        list_module_relationships = []
        list_relationships = {}
        for items in relationships:
            list_module_relationships.append(items['name'])
        for module_relation in list_module_relationships:
            data = self.get_relationships_v8(module_name, id, module_relation, True)
            if data['data'] != []:
                list_relationships[str(data['data'][0]['type'])] = data['data']
        return list_relationships

    def get_bean_list_v8(self, module_name, fields=None, filter=None, pagination=None, sort=None):
        connectors = ["?", "&"]
        connectors_idx = 0
        url = f'{self.conf.url}{self.MODULE_URL}/{module_name}'

        # Fields Constructor
        if fields:
            url += f'{connectors[connectors_idx]}fields[{module_name}]=' + ','.join(fields)
            connectors_idx = 1

        if pagination:
            if pagination.page_number != None:
                url += "{0}page[number]={1}&page[size]={2}".format(connectors[connectors_idx], pagination.page_number, pagination.page_size)
            else:
                url += "{0}page[size]={1}".format(connectors[connectors_idx], pagination.page_size)
            connectors_idx = 1
        
        if sort:
            url += f'{connectors[connectors_idx]}sort=-{sort}'
            connectors_idx = 1


        if filter:
            url += "{0}{1}".format(connectors[connectors_idx], filter.to_filter_string())
            connectors_idx = 1

        response = self._request(f'{url}', 'get')['data']
        return response

    def get_relationships_v8(self, module_name, id: str, related_module_name: str, only_relationship_fields: bool = False, link_name_to_fields_array='', fields=None) -> dict:
        """
        returns the relationship between this record and another module.
        :param module_name: name of the module
        :param id: (string) id of the current module record.
        :param related_module_name: (string) the module name you want to search relationships for, ie. Contacts.
        :param link_name_to_fields_array: a list of link_names and for each link_name.
        :param fields: (list) A list of fields you want to be returned from each related record.
        :return: (dictionary) A list of relationships that this module's record contains with the related module.
        """
        url = f'/{module_name}/{id}/relationships/{related_module_name.lower()}'
        response = self._request(f'{self.conf.url}{self.MODULE_URL}{url}', 'get')

        if only_relationship_fields:
            return response

        bean_list = []
        print(url)
        for value in response['data']:
            bean_list.append(self.get_bean_v8(value['type'], value['id'], link_name_to_fields_array=link_name_to_fields_array, fields=fields))
        return {
            "entry_list": bean_list,
            "result_count": len(bean_list),
        }

    def save_bean_v8(self, bean:Bean):
        attributes = bean.get_bean_fields()
        module = bean.module
        data = {'type': module, 'id': str(uuid.uuid4()), 'attributes': attributes}
        return self._request(f'{self.conf.url}{self.MODULE_URL}', 'post', data)

    def set_relationship_v8(self, module_name, module_id, related_names, related_ids, delete=False):
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
            return self._delete_relationship(module_name, module_id, related_names, related_ids)
        return self._create_relationship(module_name, module_id, related_names, related_ids)

    def _create_relationship(self, module_name, module_id, related_module_names, related_ids):
        # Post
        response = []
        url = f'/{module_name}/{module_id}/relationships'
        for related_module_name, related_id in zip(related_module_names, related_ids):
            data = {'type': related_module_name.capitalize(), 'id': related_id}
            response.append(self._request(f'{self.conf.url}{self.MODULE_URL}{url}', 'post', data))
        return response

    def _delete_relationship(self, module_name, module_id, related_module_names, related_ids):
        response = []
        for related_module_name, related_id in zip(related_module_names, related_ids):
            url = f'/{module_name}/{module_id}/relationships/{related_module_name.lower()}/{related_id}'
            response.append(self._request(f'{self.conf.url}{self.MODULE_URL}{url}', 'delete'))
        return response

    def get_bean(self, module_name, id, select_fields='',
                 link_name_to_fields_array='', track_view=''):
        """
        Retrieve a single Bean based on ID.

        :param str module_name: name of the module to return record from.
        :param str id: bean id.
        :param list[str] select_fields: list of the fields to be included in the results.
            This optional parameter allows for only needed fields to be retrieved.
        :param list[dict] link_name_to_fields_array: a list of link_names and for each link_name,
            what fields value to be returned.
        :param bool track_view: should we track the record accessed.
        :return: Bean object matching the selection criteria.
        :rtype: Bean
        :raises BeanNotFoundException: if the Bean is not found.
        :raises SuiteException: if error when retrieving bean from SuiteCRM instance.
        """
        parameters = OrderedDict()
        parameters['session'] = self._session_id
        parameters['module_name'] = module_name
        parameters['id'] = id
        parameters['select_fields'] = select_fields
        parameters['link_name_to_fields_array'] = link_name_to_fields_array
        parameters['track_view'] = track_view
        result = self._request('get_entry', parameters)
        if self._get_bean_failed(result):
            error_msg = result['entry_list'][0]['name_value_list'][0]['value']
            raise BeanNotFoundException(error_msg)
        return Bean(
            module_name,
            result['entry_list'][0]['name_value_list'],
            result['relationship_list'][0] if len(
                result['relationship_list']) > 0 else []
        )

    def save_bean(self, bean):
        """
        Saves a Bean object to SuiteCRM.

        :param Bean bean: Bean object.
        :raises SuiteException: if error when saving Bean to SuiteCRM instance.
        """
        parameters = OrderedDict()
        parameters['session'] = self._session_id
        parameters['module_name'] = bean.module
        parameters['name_value_list'] = bean.name_value_list
        result = self._request('set_entry', parameters)
        bean._set_name_value_list(result['entry_list'])
        bean['id'] = result['id']

    def get_bean_list(self, module_name, query='', order_by='',
                      offset='', select_fields='', link_name_to_fields_array='',
                      max_results='', deleted='', favorites=''):
        """
        Get list of beans matching criteria.

        :param str module_name: name of the module to return records from.
        :param str query: SQL WHERE clause without the word 'WHERE'.
        :param str order_by: SQL ORDER BY clause without the phrase 'ORDER BY'.
        :param int offset: the record offset to start from.
        :param list[str] select_fields: a list of the fields to be included in the results.
            This optional parameter allows for only needed fields to be retrieved.
        :param list[dict] link_name_to_fields_array: a list of link_names and for each link_name,
            what fields value to be returned.
        :param int max_results: the maximum number of records to return.
            The default is the sugar configuration value for 'list_max_entries_per_page'.
        :param bool deleted: False if deleted records should not be include,
            True if deleted records should be included.
        :param bool favorites: True if only favorites should be included, False otherwise.
        :return: dict containing results matching criteria.
        :rtype: dict[str, object]
        :raises SuiteException: if error when retrieving beans from SuiteCRM instance.
        """
        parameters = OrderedDict()
        parameters['session'] = self._session_id
        parameters['module_name'] = module_name
        parameters['query'] = query
        parameters['order_by'] = order_by
        parameters['offset'] = offset
        parameters['select_fields'] = select_fields
        parameters['link_name_to_fields_array'] = link_name_to_fields_array
        parameters['max_results'] = max_results
        parameters['deleted'] = deleted
        parameters['favorites'] = favorites
        result = self._request('get_entry_list', parameters)
        bean_list = []
        for entry in result['entry_list']:
            bean_list.append(Bean(module_name, entry['name_value_list']))
        previous_offset = None
        if offset and max_results and offset - max_results >= 0:
            previous_offset = offset - max_results
        next_offset = None
        try:
            if int(result['next_offset']) < int(result['total_count']):
                next_offset = result['next_offset']
        except Exception:
            pass
        return {
            "result_count": result['result_count'],
            "total_count": result['total_count'],
            "previous_offset": previous_offset,
            "current_offset": offset if offset else 0,
            "next_offset": next_offset,
            "current_limit": max_results,
            "entry_list": bean_list
        }

    def get_available_modules(self, filter='default'):
        """
        Retrieve the list of available modules on the system available to the currently logged in user.

        :param str filter: valid values are: [all, default, mobile].
        :return: dictionary containing information about modules.
        :rtype: dict[str, object]
        :raises SuiteException: if error when retrieving modules from SuiteCRM.
        """
        parameters = OrderedDict()
        parameters['session'] = self._session_id
        parameters['filter'] = filter
        result = self._request('get_available_modules', parameters)
        return result

    def get_module_fields(self, module_name, fields=''):
        """
        Retrieve field definitions of a module.

        :param str module_name: the name of the module to return records from.
        :param list[str] fields: if specified then retrieve definition of specified fields only.
        :return: field definitions of the specified module.
        :rtype: dict[str, object]
        :raises SuiteException: if error when retrieving field definitions from SuiteCRM.
        """
        parameters = OrderedDict()
        parameters['session'] = self._session_id
        parameters['module_name'] = module_name
        parameters['fields'] = fields
        result = self._request('get_module_fields', parameters)
        return result

    def get_relationships(self, module_name, module_id, link_field_name,
                          related_module_query='', related_fields=None,
                          related_module_link_name_to_fields_array=None, deleted=False,
                          order_by='', offset='', limit=''):
        """
        Retrieve a collection of beans that are related to the specified bean
        and optionally return relationship data for those related beans.

        :param str module_name: name of the module that the primary record is from.
        :param str module_id: ID of the bean in the specified module.
        :param str link_field_name: name of the link field to return records from.
        :param str related_module_query: a portion of the where clause of the SQL statement to find the related items.
            The SQL query will already be filtered to only include the beans that are related to the specified bean.
        :param list[str] related_fields: list of related bean fields to be returned.
        :param list[dict] related_module_link_name_to_fields_array: for every related bean returned,
            specify link fields name to fields info for that bean to be returned.
        :param bool deleted: False if deleted records should not be include,
            True if deleted records should be included.
        :param str order_by: SQL ORDER BY clause without the phrase 'ORDER BY'.
        :param int offset: the result offset to start from.
        :param int limit: the maximum number of records to return.
        :return: dict containing results matching criteria.
        :rtype: dict[str, object]
        :raises SuiteException: if error when retrieving beans from SuiteCRM instance.
        """
        parameters = OrderedDict()
        parameters['session'] = self._session_id
        parameters['module_name'] = module_name
        parameters['module_id'] = module_id
        parameters['link_field_name'] = link_field_name
        parameters['related_module_query'] = related_module_query
        parameters['related_fields'] = related_fields or []
        parameters['related_module_link_name_to_fields_array'] = \
            related_module_link_name_to_fields_array or []
        parameters['deleted'] = deleted
        parameters['order_by'] = order_by
        parameters['offset'] = offset
        parameters['limit'] = limit
        result = self._request('get_relationships', parameters)
        bean_list = []
        for i, entry in enumerate(result['entry_list']):
            bean_list.append(
                Bean(
                    entry['module_name'],
                    entry['name_value_list'],
                    result['relationship_list'][i] if len(
                        result['relationship_list']) > i else []
                )
            )
        previous_offset = None
        result_count = len(bean_list)
        if offset and limit and offset - limit >= 0:
            previous_offset = offset - limit
        next_offset = None
        if limit and result_count == limit:
            if offset:
                next_offset = offset + limit
            else:
                next_offset = limit
        return {
            "entry_list": bean_list,
            "result_count": result_count,
            "previous_offset": previous_offset,
            "current_offset": offset if offset else 0,
            "next_offset": next_offset,
            "current_limit": limit
        }

    def set_relationship(self, module_name, module_id, link_field_name,
                         related_ids, name_value_list=None, delete=False):
        """
        Set a single relationship between two beans. The items are related by module name and id.

        :param str module_name: name of the module that the primary record is from.
        :param str module_id: ID of the bean in the specified module_name.
        :param str link_field_name: name of the link field which relates to the other
            module for which the relationship needs to be generated.
        :param list[str] related_ids: list of related record ids for which relationships needs to be generated.
        :param dict[str, str] name_value_list: the keys of the array are the SugarBean attributes,
            the values of the array are the values the attributes should have.
        :param bool delete: if True delete the relationship and if False add the relationship.
        :return: how many relationships are deleted, created and failed.
        :rtype: dict[str, int]
        :raises SuiteException: if error when relating beans.
        """
        parameters = OrderedDict()
        parameters['session'] = self._session_id
        parameters['module_name'] = module_name
        parameters['module_id'] = module_id
        parameters['link_field_name'] = link_field_name
        parameters['related_ids'] = related_ids
        parameters['name_value_list'] = name_value_list or []
        parameters['delete'] = delete
        return self._request('set_relationship', parameters)

    def get_note_attachment(self, note_id):
        """
        Retrieve an attachment from a note.

        :param str note_id: ID of the appropriate Note.
        :return: the requested attachment.
        :rtype: dict[str, object]
        :raises SuiteException: if error when retrieving the attachment from SuiteCRM instance.
        """
        parameters = OrderedDict()
        parameters['session'] = self._session_id
        parameters['id'] = note_id
        return self._request('get_note_attachment', parameters)

    def set_note_attachment(self, note_id, filename, file):
        """
        Add or replace the attachment on a Note.

        :param str note_id: ID of the Note containing the attachment.
        :param str filename: the file name of the attachment.
        :param str file: the binary contents of the file.
        :return: the ID of the note.
        :rtype: dict[str, str]
        :raises SuiteException: if error when setting the note attachment.
        """
        parameters = OrderedDict()
        parameters['session'] = self._session_id
        parameters['note'] = {
            'id': note_id,
            'filename': filename,
            'file': file
        }
        return self._request('set_note_attachment', parameters)

    def get_pdf_template(self, template_id, bean_module, bean_id):
        """
        Retrieve PDF Template for a given module record.

        :param str template_id: template ID used to generate PDF.
        :param str bean_module: module name of the bean that will be used to populate PDF.
        :param str bean_id: ID of the bean record.
        :return: the generated PDF.
        :rtype: dict[str, str]
        :raises SuiteException: if error when retrieving PDF.
        """
        parameters = OrderedDict()
        parameters['session'] = self._session_id
        parameters['template_id'] = template_id
        parameters['bean_module'] = bean_module
        parameters['bean_id'] = bean_id
        return self._request('get_pdf_template', parameters)
