# -*- coding: utf-8 -*-

"""
 (c) 2016 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""

__requires__ = ['SQLAlchemy >= 0.8']
import pkg_resources

import datetime
import unittest
import sys
import time
import os

import flask
import flask_wtf
from mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(
    os.path.abspath(__file__)), '..'))

import pagure.forms
import tests


class PagureFlaskFormTests(tests.Modeltests):
    """ Tests for forms of the flask application """

    def setUpt(self):
        pagure.APP.config['TESTING'] = True
        pagure.APP.config['SERVER_NAME'] = 'pagure.org'
        pagure.SESSION = self.session
        self.app = pagure.APP.test_client()

    def test_csrf_form_no_input(self):
        """ Test the CSRF validation if not CSRF is specified. """
        with pagure.APP.test_request_context(method='POST'):
            form = pagure.forms.ConfirmationForm()
            self.assertFalse(form.validate_on_submit())

    def test_csrf_form_w_invalid_input(self):
        """ Test the CSRF validation with an invalid CSRF specified. """
        with pagure.APP.test_request_context(method='POST'):
            form = pagure.forms.ConfirmationForm()
            form.csrf_token.data = 'foobar'
            self.assertFalse(form.validate_on_submit())

    def test_csrf_form_w_input(self):
        """ Test the CSRF validation with a valid CSRF specified. """
        with pagure.APP.test_request_context(method='POST'):
            form = pagure.forms.ConfirmationForm()
            form.csrf_token.data = form.csrf_token.current_token
            self.assertTrue(form.validate_on_submit())

    def test_csrf_form_w_expired_input(self):
        """ Test the CSRF validation with an expired CSRF specified. """
        with pagure.APP.test_request_context(method='POST'):
            form = pagure.forms.ConfirmationForm()
            data = form.csrf_token.current_token

            # CSRF token expired
            if hasattr(flask_wtf, '__version__') and \
                    tuple(flask_wtf.__version__.split('.')) >= (0,10,0):
                expires = time.time() - 1
            else:
                expires = (
                    datetime.datetime.now() - datetime.timedelta(minutes=1)
                ).strftime('%Y%m%d%H%M%S')

            # Change the CSRF format
            if hasattr(flask_wtf, '__version__') and \
                    tuple([int(e) for e in flask_wtf.__version__.split('.')]
                    ) >= (0,14,0):
                import itsdangerous
                timestamp = itsdangerous.base64_encode(
                    itsdangerous.int_to_bytes(int(expires)))
                print '*', data
                part1, _, part2 = data.split('.', 2)
                form.csrf_token.data = '.'.join([part1, timestamp, part2])
            else:
                _, hmac_csrf = data.split('##', 1)
                form.csrf_token.data = '%s##%s' % (expires, hmac_csrf)

            self.assertFalse(form.validate_on_submit())

    def test_csrf_form_w_unexpiring_input(self):
        """ Test the CSRF validation with a CSRF not expiring. """
        pagure.APP.config['WTF_CSRF_TIME_LIMIT'] = None
        with pagure.APP.test_request_context(method='POST'):
            form = pagure.forms.ConfirmationForm()
            data = form.csrf_token.current_token

            if hasattr(flask_wtf, '__version__') and \
                    tuple([int(e) for e in flask_wtf.__version__.split('.')]
                    ) >= (0,14,0):
                form.csrf_token.data = data
            else:
                _, hmac_csrf = data.split('##', 1)
                # CSRF can no longer expire, they have no expiration info
                form.csrf_token.data = '##%s' % hmac_csrf
            self.assertTrue(form.validate_on_submit())

    def test_add_user_form(self):
        """ Test the AddUserForm of pagure.forms """
        with pagure.APP.test_request_context(method='POST'):
            form = pagure.forms.AddUserForm()
            form.csrf_token.data = form.csrf_token.current_token
            # No user or access given
            self.assertFalse(form.validate_on_submit())
            # No access given
            form.user.data = 'foo'
            self.assertFalse(form.validate_on_submit())
            form.access.data = 'admin'
            self.assertTrue(form.validate_on_submit())

    def test_add_user_to_group_form(self):
        """ Test the AddUserToGroup form of pagure.forms """
        with pagure.APP.test_request_context(method='POST'):
            form = pagure.forms.AddUserToGroupForm()
            form.csrf_token.data = form.csrf_token.current_token
            # No user given
            self.assertFalse(form.validate_on_submit())
            form.user.data = 'foo'
            # Everything given
            self.assertTrue(form.validate_on_submit())

    def test_add_group_form(self):
        """ Test the AddGroupForm form of pagure.forms """
        with pagure.APP.test_request_context(method='POST'):
            form = pagure.forms.AddGroupForm()
            form.csrf_token.data = form.csrf_token.current_token
            # No group given
            self.assertFalse(form.validate_on_submit())
            # No access given
            form.group.data = 'gname'
            self.assertFalse(form.validate_on_submit())
            form.access.data = 'admin'
            self.assertTrue(form.validate_on_submit())


if __name__ == '__main__':
    unittest.main(verbosity=2)

