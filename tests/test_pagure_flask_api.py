# -*- coding: utf-8 -*-

"""
 (c) 2015 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""

from __future__ import unicode_literals

__requires__ = ['SQLAlchemy >= 0.8']
import pkg_resources

import unittest
import shutil
import sys
import os

import json
from mock import patch, MagicMock

sys.path.insert(0, os.path.join(os.path.dirname(
    os.path.abspath(__file__)), '..'))

import pagure.api
import pagure.flask_app
import pagure.lib.query
import tests


class PagureFlaskApitests(tests.SimplePagureTest):
    """ Tests for flask API controller of pagure """

    maxDiff = None

    def test_api_doc(self):
        """ Test the API documentation page. """
        print(dir(self.app))
        output = self.app.get('/api/0/')
        output_text = output.get_data(as_text=True)
        self.assertIn(
            '<title> API | pagure  - Pagure</title>\n', output_text)
        self.assertIn(
            '&nbsp; Pagure API Reference\n        </h2>\n', output_text)

    def test_api_doc_authenticated(self):
        """ Test the API documentation page. """
        user = tests.FakeUser(username='foo')
        with tests.user_set(self.app.application, user):
            output = self.app.get('/api/0/')
            output_text = output.get_data(as_text=True)
            self.assertIn(
                '<title> API | pagure  - Pagure</title>\n', output_text)
            self.assertIn(
                '&nbsp; Pagure API Reference\n        </h2>\n', output_text)

    def test_api_get_request_data(self):
        data = {'foo': 'bar'}
        # test_request_context doesn't set flask.g, but some teardown
        # functions try to use that, so let's exclude them
        self._app.teardown_request_funcs = {}
        with self._app.test_request_context('/api/0/version', data=data):
            self.assertEqual(pagure.api.get_request_data()['foo'], 'bar')
        data = json.dumps(data)
        with self._app.test_request_context('/api/0/version', data=data,
                                            content_type='application/json'):
            self.assertEqual(pagure.api.get_request_data()['foo'], 'bar')

    def test_api_version_old_url(self):
        """ Test the api_version function.  """
        output = self.app.get('/api/0/version')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.get_data(as_text=True))
        self.assertEqual(data['version'], pagure.__api_version__)
        self.assertEqual(sorted(data.keys()), ['version'])

    def test_api_version_new_url(self):
        """ Test the api_version function at its new url.  """
        output = self.app.get('/api/0/-/version')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.get_data(as_text=True))
        self.assertEqual(data['version'], pagure.__api_version__)
        self.assertEqual(sorted(data.keys()), ['version'])

    def test_api_project_tags(self):
        """ Test the api_project_tags function.  """
        tests.create_projects(self.session)

        output = self.app.get('/api/0/foo/tags/')
        self.assertEqual(output.status_code, 404)
        data = json.loads(output.get_data(as_text=True))
        self.assertEqual(set(data.keys()), set(['output', 'error']))
        self.assertEqual(data['output'], 'notok')
        self.assertEqual(data['error'], 'Project not found')

        output = self.app.get('/api/0/test/tags/')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.get_data(as_text=True))
        self.assertEqual(sorted(data.keys()), ['tags', 'total_tags'])
        self.assertEqual(data['tags'], [])
        self.assertEqual(data['total_tags'], 0)

        # Add an issue and tag it so that we can list them
        item = pagure.lib.model.Issue(
            id=1,
            uid='foobar',
            project_id=1,
            title='issue',
            content='a bug report',
            user_id=1,  # pingou
        )
        self.session.add(item)
        self.session.commit()
        item = pagure.lib.model.TagColored(
            tag='tag1', tag_color='DeepBlueSky', project_id=1,
        )
        self.session.add(item)
        self.session.commit()
        item = pagure.lib.model.TagIssueColored(
            issue_uid='foobar',
            tag_id=item.id
        )
        self.session.add(item)
        self.session.commit()

        output = self.app.get('/api/0/test/tags/')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.get_data(as_text=True))
        self.assertEqual(sorted(data.keys()), ['tags', 'total_tags'])
        self.assertEqual(data['tags'], ['tag1'])
        self.assertEqual(data['total_tags'], 1)

        output = self.app.get('/api/0/test/tags/?pattern=t')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.get_data(as_text=True))
        self.assertEqual(sorted(data.keys()), ['tags', 'total_tags'])
        self.assertEqual(data['tags'], ['tag1'])
        self.assertEqual(data['total_tags'], 1)

        output = self.app.get('/api/0/test/tags/?pattern=p')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.get_data(as_text=True))
        self.assertEqual(sorted(data.keys()), ['tags', 'total_tags'])
        self.assertEqual(data['tags'], [])
        self.assertEqual(data['total_tags'], 0)

    def test_api_groups(self):
        """ Test the api_groups function.  """

        # Add a couple of groups so that we can list them
        item = pagure.lib.model.PagureGroup(
            group_name='group1',
            group_type='user',
            display_name='User group',
            user_id=1,  # pingou
        )
        self.session.add(item)

        item = pagure.lib.model.PagureGroup(
            group_name='rel-eng',
            group_type='user',
            display_name='Release engineering group',
            user_id=1,  # pingou
        )
        self.session.add(item)
        self.session.commit()

        output = self.app.get('/api/0/groups')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.get_data(as_text=True))
        self.assertEqual(data['groups'], ['group1', 'rel-eng'])
        self.assertEqual(
            sorted(data.keys()),
            ['groups', 'pagination', 'total_groups'])
        self.assertEqual(data['total_groups'], 2)

        output = self.app.get('/api/0/groups?pattern=re')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.get_data(as_text=True))
        self.assertEqual(data['groups'], ['rel-eng'])
        self.assertEqual(
            sorted(data.keys()),
            ['groups', 'pagination', 'total_groups'])
        self.assertEqual(data['total_groups'], 1)

    def test_api_whoami_unauth(self):
        """ Test the api_whoami function. """

        output = self.app.post('/api/0/-/whoami')
        self.assertEqual(output.status_code, 401)
        data = json.loads(output.get_data(as_text=True))
        self.assertEqual(
            data,
            {
                u'error': u'Invalid or expired token. Please visit '
                'http://localhost.localdomain/settings#api-keys to get or '
                'renew your API token.',
                u'error_code': u'EINVALIDTOK'
            }
        )

    def test_api_whoami_invalid_auth(self):
        """ Test the api_whoami function with an invalid token. """
        tests.create_projects(self.session)
        tests.create_tokens(self.session)

        headers = {'Authorization': 'token invalid'}

        output = self.app.post('/api/0/-/whoami', headers=headers)
        self.assertEqual(output.status_code, 401)
        data = json.loads(output.get_data(as_text=True))
        self.assertEqual(
            data,
            {
                u'error': u'Invalid or expired token. Please visit '
                'http://localhost.localdomain/settings#api-keys to get or '
                'renew your API token.',
                u'error_code': u'EINVALIDTOK'
            }
        )

    def test_api_whoami_auth(self):
        """ Test the api_whoami function with a valid token. """
        tests.create_projects(self.session)
        tests.create_tokens(self.session)

        headers = {'Authorization': 'token aaabbbcccddd'}

        output = self.app.post('/api/0/-/whoami', headers=headers)
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.get_data(as_text=True))
        self.assertEqual(data, {u'username': u'pingou'})

    def test_api_error_codes(self):
        """ Test the api_error_codes endpoint. """
        output = self.app.get('/api/0/-/error_codes')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.get_data(as_text=True))
        self.assertEqual(len(data), 33)
        self.assertEqual(
            sorted(data.keys()),
            [
                u'EDATETIME', u'EDBERROR', u'EGITERROR',
                u'EINVALIDISSUEFIELD', u'EINVALIDISSUEFIELD_LINK',
                u'EINVALIDPERPAGEVALUE', u'EINVALIDPRIORITY', u'EINVALIDREQ',
                u'EINVALIDTOK', u'EISSUENOTALLOWED',
                u'EMODIFYPROJECTNOTALLOWED', u'ENEWPROJECTDISABLED',
                u'ENOCODE', u'ENOCOMMENT', u'ENOCOMMIT', u'ENOGROUP',
                u'ENOISSUE', u'ENOPRCLOSE', u'ENOPROJECT', u'ENOPROJECTS',
                u'ENOPRSTATS', u'ENOREQ', u'ENOSIGNEDOFF', u'ENOTASSIGNED',
                u'ENOTASSIGNEE', u'ENOTHIGHENOUGH', u'ENOTMAINADMIN',
                u'ENOUSER', u'EPRSCORE', u'EPULLREQUESTSDISABLED',
                u'ETIMESTAMP', u'ETRACKERDISABLED', u'ETRACKERREADONLY'
            ]
        )

    @patch("pagure.lib.tasks.get_result")
    def test_api_task_status(self, get_result):
        async_result = MagicMock()
        async_result.status = "running"
        async_result.ready.return_value = False
        get_result.return_value = async_result
        output = self.app.get("/api/0/task/123abc/status/")
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.get_data(as_text=True))
        self.assertEqual(data, {"ready": False, "status": "running"})

        async_result = MagicMock()
        async_result.status = "finished"
        async_result.ready.return_value = True
        async_result.successful.return_value = True
        get_result.return_value = async_result
        output = self.app.get("/api/0/task/123abc/status/")
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.get_data(as_text=True))
        self.assertEqual(
            data,
            {"ready": True, "status": "finished", "successful": True}
        )


if __name__ == '__main__':
    unittest.main(verbosity=2)
