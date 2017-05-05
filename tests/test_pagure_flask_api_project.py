# -*- coding: utf-8 -*-

"""
 (c) 2015-2017 - Copyright Red Hat Inc

 Authors:
   Pierre-Yves Chibon <pingou@pingoured.fr>

"""

__requires__ = ['SQLAlchemy >= 0.8']
import pkg_resources

import datetime
import json
import unittest
import shutil
import sys
import tempfile
import os


import pygit2
from mock import patch

sys.path.insert(0, os.path.join(os.path.dirname(
    os.path.abspath(__file__)), '..'))

import pagure.lib
import tests
from pagure.lib.repo import PagureRepo


class PagureFlaskApiProjecttests(tests.Modeltests):
    """ Tests for the flask API of pagure for issue """

    def setUp(self):
        """ Set up the environnment, ran before every tests. """
        super(PagureFlaskApiProjecttests, self).setUp()

        pagure.APP.config['TESTING'] = True
        pagure.SESSION = self.session
        pagure.api.SESSION = self.session
        pagure.api.project.SESSION = self.session
        pagure.lib.SESSION = self.session

        pagure.APP.config['GIT_FOLDER'] = os.path.join(self.path, 'repos')
        pagure.APP.config['REQUESTS_FOLDER'] = os.path.join(
            self.path, 'requests')
        pagure.APP.config['TICKETS_FOLDER'] = os.path.join(
            self.path, 'tickets')
        pagure.APP.config['DOCS_FOLDER'] = os.path.join(
            self.path, 'docs')

        self.app = pagure.APP.test_client()

    def test_api_git_tags(self):
        """ Test the api_git_tags method of the flask api. """
        tests.create_projects(self.session)

        # Create a git repo to play with
        gitrepo = os.path.join(self.path, 'repos', 'test.git')
        repo = pygit2.init_repository(gitrepo, bare=True)

        newpath = tempfile.mkdtemp(prefix='pagure-fork-test')
        repopath = os.path.join(newpath, 'test')
        clone_repo = pygit2.clone_repository(gitrepo, repopath)

        # Create a file in that git repo
        with open(os.path.join(repopath, 'sources'), 'w') as stream:
            stream.write('foo\n bar')
        clone_repo.index.add('sources')
        clone_repo.index.write()

        # Commits the files added
        tree = clone_repo.index.write_tree()
        author = pygit2.Signature(
            'Alice Author', 'alice@authors.tld')
        committer = pygit2.Signature(
            'Cecil Committer', 'cecil@committers.tld')
        clone_repo.create_commit(
            'refs/heads/master',  # the name of the reference to update
            author,
            committer,
            'Add sources file for testing',
            # binary string representing the tree object ID
            tree,
            # list of binary strings representing parents of the new commit
            []
        )
        refname = 'refs/heads/master:refs/heads/master'
        ori_remote = clone_repo.remotes[0]
        PagureRepo.push(ori_remote, refname)

        # Tag our first commit
        first_commit = repo.revparse_single('HEAD')
        tagger = pygit2.Signature('Alice Doe', 'adoe@example.com', 12347, 0)
        repo.create_tag(
            "0.0.1", first_commit.oid.hex, pygit2.GIT_OBJ_COMMIT, tagger,
            "Release 0.0.1")

        # Check tags
        output = self.app.get('/api/0/test/git/tags')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {'tags': ['0.0.1'], 'total_tags': 1}
        )

        shutil.rmtree(newpath)

    def test_api_git_branches(self):
        """ Test the api_git_branches method of the flask api. """
        # Create a git repo to add branches to
        tests.create_projects(self.session)
        repo_path = os.path.join(self.path, 'repos', 'test.git')
        tests.add_content_git_repo(repo_path)
        new_repo_path = tempfile.mkdtemp(prefix='pagure-api-git-branches-test')
        clone_repo = pygit2.clone_repository(repo_path, new_repo_path)

        # Create two other branches based on master
        for branch in ['pats-win-49', 'pats-win-51']:
            clone_repo.create_branch(branch, clone_repo.head.get_object())
            refname = 'refs/heads/{0}:refs/heads/{0}'.format(branch)
            PagureRepo.push(clone_repo.remotes[0], refname)

        # Check that the branches show up on the API
        output = self.app.get('/api/0/test/git/branches')
        # Delete the cloned git repo after the API call
        shutil.rmtree(new_repo_path)

        # Verify the API data
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
                'branches': ['master', 'pats-win-49', 'pats-win-51'],
                'total_branches': 3
            }
        )

    def test_api_git_branches_empty_repo(self):
        """ Test the api_git_branches method of the flask api when the repo is
        empty.
        """
        # Create a git repo without any branches
        tests.create_projects(self.session)
        repo_base_path = os.path.join(self.path, 'repos')
        tests.create_projects_git(repo_base_path)

        # Check that no branches show up on the API
        output = self.app.get('/api/0/test/git/branches')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
                'branches': [],
                'total_branches': 0
            }
        )

    def test_api_git_branches_no_repo(self):
        """ Test the api_git_branches method of the flask api when there is no
        repo on a project.
        """
        tests.create_projects(self.session)
        output = self.app.get('/api/0/test/git/branches')
        self.assertEqual(output.status_code, 404)

    def test_api_projects(self):
        """ Test the api_projects method of the flask api. """
        tests.create_projects(self.session)

        # Check before adding
        repo = pagure.get_authorized_project(self.session, 'test')
        self.assertEqual(repo.tags, [])

        # Adding a tag
        output = pagure.lib.update_tags(
            self.session, repo, 'infra', 'pingou',
            None)
        self.assertEqual(output, ['Issue tagged with: infra'])

        # Check after adding
        repo = pagure.get_authorized_project(self.session, 'test')
        self.assertEqual(len(repo.tags), 1)
        self.assertEqual(repo.tags_text, ['infra'])

        # Check the API
        output = self.app.get('/api/0/projects?tags=inf')
        self.assertEqual(output.status_code, 404)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {'error_code': 'ENOPROJECTS', 'error': 'No projects found'}
        )
        output = self.app.get('/api/0/projects?tags=infra')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        data['projects'][0]['date_created'] = "1436527638"
        expected_data = {
            "args": {
                "fork": None,
                "namespace": None,
                "pattern": None,
                "tags": ["infra"],
                "username": None
            },
            "projects": [{
                "access_groups": {
                    "admin": [],
                    "commit": [],
                    "ticket": []},
                "access_users": {
                     "admin": [],
                     "commit": [],
                     "owner": ["pingou"],
                     "ticket": []},
                "close_status": [
                    "Invalid",
                    "Insufficient data",
                    "Fixed",
                    "Duplicate"
                ],
                "custom_keys": [],
                "date_created": "1436527638",
                "description": "test project #1",
                "fullname": "test",
                "id": 1,
                "milestones": {},
                "name": "test",
                "namespace": None,
                "parent": None,
                "priorities": {},
                "tags": ["infra"],
                "user": {
                    "fullname": "PY C",
                    "name": "pingou"
                }
            }],
            "total_projects": 1
        }
        self.assertDictEqual(data, expected_data)

        output = self.app.get('/api/0/projects?username=pingou')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        data['projects'][0]['date_created'] = "1436527638"
        data['projects'][1]['date_created'] = "1436527638"
        data['projects'][2]['date_created'] = "1436527638"
        expected_data = {
            "args": {
                "fork": None,
                "namespace": None,
                "pattern": None,
                "tags": [],
                "username": "pingou"
            },
            "projects": [
                {
                    "access_groups": {
                        "admin": [],
                        "commit": [],
                        "ticket": []},
                    "access_users": {
                        "admin": [],
                        "commit": [],
                        "owner": ["pingou"],
                        "ticket": []
                    },
                    "close_status": [
                        "Invalid",
                        "Insufficient data",
                        "Fixed",
                        "Duplicate"
                    ],
                    "custom_keys": [],
                    "date_created": "1436527638",
                    "description": "test project #1",
                    "fullname": "test",
                    "id": 1,
                    "milestones": {},
                    "name": "test",
                    "namespace": None,
                    "parent": None,
                    "priorities": {},
                    "tags": ["infra"],
                    "user": {
                        "fullname": "PY C",
                        "name": "pingou"
                    }
                },
                {
                    "access_groups": {
                        "admin": [],
                        "commit": [],
                        "ticket": []
                    },
                    "access_users": {
                        "admin": [],
                        "commit": [],
                        "owner": ["pingou"],
                        "ticket": []
                    },
                    "close_status": [
                        "Invalid",
                        "Insufficient data",
                        "Fixed",
                        "Duplicate"
                    ],
                    "custom_keys": [],
                    "date_created": "1436527638",
                    "description": "test project #2",
                    "fullname": "test2",
                    "id": 2,
                    "milestones": {},
                    "name": "test2",
                    "namespace": None,
                    "parent": None,
                    "priorities": {},
                    "tags": [],
                    "user": {
                        "fullname": "PY C",
                        "name": "pingou"
                    }
                },
                {
                    "access_groups": {
                        "admin": [],
                        "commit": [],
                        "ticket": []},
                    "access_users": {
                        "admin": [],
                        "commit": [],
                        "owner": ["pingou"],
                        "ticket": []},
                    "close_status": [
                        "Invalid",
                        "Insufficient data",
                        "Fixed",
                        "Duplicate"
                    ],
                    "custom_keys": [],
                    "date_created": "1436527638",
                    "description": "namespaced test project",
                    "fullname": "somenamespace/test3",
                    "id": 3,
                    "milestones": {},
                    "name": "test3",
                    "namespace": "somenamespace",
                    "parent": None,
                    "priorities": {},
                    "tags": [],
                    "user": {
                        "fullname": "PY C",
                        "name": "pingou"
                    }
                }
            ],
            "total_projects": 3
        }
        self.assertDictEqual(data, expected_data)

        output = self.app.get('/api/0/projects?username=pingou&tags=infra')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        data['projects'][0]['date_created'] = "1436527638"
        expected_data = {
            "args": {
                "fork": None,
                "namespace": None,
                "pattern": None,
                "tags": ["infra"],
                "username": "pingou",
            },
            "projects": [{
                "access_groups": {
                    "admin": [],
                    "commit": [],
                    "ticket": []
                },
                "access_users": {
                    "admin": [],
                    "commit": [],
                    "owner": ["pingou"],
                    "ticket": []},
                "close_status": [
                    "Invalid",
                    "Insufficient data",
                    "Fixed",
                    "Duplicate"],
                "custom_keys": [],
                "date_created": "1436527638",
                "description": "test project #1",
                "fullname": "test",
                "id": 1,
                "milestones": {},
                "name": "test",
                "namespace": None,
                "parent": None,
                "priorities": {},
                "tags": ["infra"],
                "user": {
                    "fullname": "PY C",
                    "name": "pingou"
                }
            }],
            "total_projects": 1
        }
        self.assertDictEqual(data, expected_data)

        output = self.app.get('/api/0/projects?namespace=somenamespace')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        data['projects'][0]['date_created'] = "1436527638"
        expected_data = {
            "args": {
                "fork": None,
                "namespace": "somenamespace",
                "pattern": None,
                "tags": [],
                "username": None
            },
            "projects": [
                {
                    "access_groups": {
                        "admin": [],
                        "commit": [],
                        "ticket": []},
                    "access_users": {
                        "admin": [],
                        "commit": [],
                        "owner": ["pingou"],
                        "ticket": []},
                    "close_status": [
                        "Invalid",
                        "Insufficient data",
                        "Fixed",
                        "Duplicate"
                    ],
                    "custom_keys": [],
                    "date_created": "1436527638",
                    "description": "namespaced test project",
                    "fullname": "somenamespace/test3",
                    "id": 3,
                    "milestones": {},
                    "name": "test3",
                    "namespace": "somenamespace",
                    "parent": None,
                    "priorities": {},
                    "tags": [],
                    "user": {
                        "fullname": "PY C",
                        "name": "pingou"
                    }
                }
            ],
            "total_projects": 1
        }
        self.assertDictEqual(data, expected_data)

    def test_api_project(self):
        """ Test the api_project method of the flask api. """
        tests.create_projects(self.session)

        # Check before adding
        repo = pagure.get_authorized_project(self.session, 'test')
        self.assertEqual(repo.tags, [])

        # Adding a tag
        output = pagure.lib.update_tags(
            self.session, repo, 'infra', 'pingou',
            ticketfolder=None)
        self.assertEqual(output, ['Issue tagged with: infra'])

        # Check after adding
        repo = pagure.get_authorized_project(self.session, 'test')
        self.assertEqual(len(repo.tags), 1)
        self.assertEqual(repo.tags_text, ['infra'])

        # Check the API

        # Non-existing project
        output = self.app.get('/api/0/random')
        self.assertEqual(output.status_code, 404)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {'error_code': 'ENOPROJECT', 'error': 'Project not found'}
        )

        # Existing project
        output = self.app.get('/api/0/test')
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        data['date_created'] = "1436527638"
        expected_data ={
            "access_groups": {
                "admin": [],
                "commit": [],
                "ticket": []
            },
            "access_users": {
                "admin": [],
                "commit": [],
                "owner": ["pingou"],
                "ticket": []},
            "close_status": [
                "Invalid",
                "Insufficient data",
                "Fixed",
                "Duplicate"
            ],
            "custom_keys": [],
            "date_created": "1436527638",
            "description": "test project #1",
            "fullname": "test",
            "id": 1,
            "milestones": {},
            "name": "test",
            "namespace": None,
            "parent": None,
            "priorities": {},
            "tags": ["infra"],
            "user": {
                "fullname": "PY C",
                "name": "pingou"
            }
        }
        self.assertDictEqual(data, expected_data)

    def test_api_project_watchers(self):
        """ Test the api_project_watchers method of the flask api. """
        tests.create_projects(self.session)
        # The user is not logged in and the owner is watching issues implicitly
        output = self.app.get('/api/0/test/watchers')
        self.assertEqual(output.status_code, 200)
        expected_data = {
            "total_watchers": 1,
            "watchers": {
                "pingou": [
                    "issues"
                ]
            }
        }
        self.assertDictEqual(json.loads(output.data), expected_data)

        user = pagure.SESSION.query(pagure.lib.model.User).filter_by(
            user='pingou')
        with tests.user_set(pagure.APP, user):
            # Non-existing project
            output = self.app.get('/api/0/random/watchers')
            self.assertEqual(output.status_code, 404)
            data = json.loads(output.data)
            self.assertDictEqual(
                data,
                {'error_code': 'ENOPROJECT', 'error': 'Project not found'}
            )

            # The owner is watching issues implicitly
            output = self.app.get('/api/0/test/watchers')
            self.assertEqual(output.status_code, 200)
            expected_data = {
                "total_watchers": 1,
                "watchers": {
                    "pingou": [
                        "issues"
                    ]
                }
            }
            self.assertDictEqual(json.loads(output.data), expected_data)

            project = pagure.get_authorized_project(self.session, 'test')

            # The owner is watching issues and commits explicitly
            pagure.lib.update_watch_status(
                pagure.SESSION, project, 'pingou', '3')
            output = self.app.get('/api/0/test/watchers')
            self.assertEqual(output.status_code, 200)
            expected_data = {
                "total_watchers": 1,
                "watchers": {
                    "pingou": [
                        "issues",
                        "commits"
                    ]
                }
            }
            self.assertDictEqual(json.loads(output.data), expected_data)

            # The owner is watching issues explicitly
            pagure.lib.update_watch_status(
                pagure.SESSION, project, 'pingou', '1')
            output = self.app.get('/api/0/test/watchers')
            self.assertEqual(output.status_code, 200)
            expected_data = {
                "total_watchers": 1,
                "watchers": {
                    "pingou": [
                        "issues"
                    ]
                }
            }
            self.assertDictEqual(json.loads(output.data), expected_data)

            # The owner is watching commits explicitly
            pagure.lib.update_watch_status(
                pagure.SESSION, project, 'pingou', '2')
            output = self.app.get('/api/0/test/watchers')
            self.assertEqual(output.status_code, 200)
            expected_data = {
                "total_watchers": 1,
                "watchers": {
                    "pingou": [
                        "commits"
                    ]
                }
            }
            self.assertDictEqual(json.loads(output.data), expected_data)

            # The owner is watching commits explicitly and foo is watching
            # issues implicitly
            project_user = pagure.lib.model.ProjectUser(
                project_id=project.id,
                user_id=2,
                access='commit',
            )
            pagure.lib.update_watch_status(
                pagure.SESSION, project, 'pingou', '2')
            pagure.SESSION.add(project_user)
            pagure.SESSION.commit()

            output = self.app.get('/api/0/test/watchers')
            self.assertEqual(output.status_code, 200)
            expected_data = {
                "total_watchers": 2,
                "watchers": {
                    "foo": ["issues"],
                    "pingou": ["commits"]
                }
            }
            self.assertDictEqual(json.loads(output.data), expected_data)

            # The owner and foo are watching issues implicitly
            pagure.lib.update_watch_status(
                pagure.SESSION, project, 'pingou', '-1')

            output = self.app.get('/api/0/test/watchers')
            self.assertEqual(output.status_code, 200)
            expected_data = {
                "total_watchers": 2,
                "watchers": {
                    "foo": ["issues"],
                    "pingou": ["issues"]
                }
            }
            self.assertDictEqual(json.loads(output.data), expected_data)

            # The owner and foo through group membership are watching issues
            # implicitly
            pagure.lib.update_watch_status(
                pagure.SESSION, project, 'pingou', '-1')
            project_membership = pagure.SESSION.query(
                pagure.lib.model.ProjectUser).filter_by(
                    user_id=2, project_id=project.id).one()
            pagure.SESSION.delete(project_membership)
            pagure.SESSION.commit()
            msg = pagure.lib.add_group(
                self.session,
                group_name='some_group',
                display_name='Some Group',
                description=None,
                group_type='bar',
                user='pingou',
                is_admin=False,
                blacklist=[],
            )
            pagure.SESSION.commit()
            group = pagure.SESSION.query(pagure.lib.model.PagureGroup)\
                .filter_by(group_name='some_group').one()
            pagure.lib.add_user_to_group(
                pagure.SESSION, 'foo', group, 'pingou', False)
            project_group = pagure.lib.model.ProjectGroup(
                project_id=project.id,
                group_id=group.id,
                access='commit',
            )
            pagure.SESSION.add(project_group)
            pagure.SESSION.commit()

            output = self.app.get('/api/0/test/watchers')
            self.assertEqual(output.status_code, 200)
            expected_data = {
                "total_watchers": 2,
                "watchers": {
                    "foo": ["issues"],
                    "pingou": ["issues"]
                }
            }
            self.assertDictEqual(json.loads(output.data), expected_data)

            # The owner is watching issues implicitly and foo will be watching
            # commits explicitly but is in a group with commit access
            pagure.lib.update_watch_status(
                pagure.SESSION, project, 'pingou', '-1')
            pagure.lib.update_watch_status(
                pagure.SESSION, project, 'foo', '2')

            output = self.app.get('/api/0/test/watchers')
            self.assertEqual(output.status_code, 200)
            expected_data = {
                "total_watchers": 2,
                "watchers": {
                    "foo": ["commits"],
                    "pingou": ["issues"]
                }
            }
            self.assertDictEqual(json.loads(output.data), expected_data)

    @patch('pagure.lib.git.generate_gitolite_acls')
    def test_api_new_project(self, p_gga):
        """ Test the api_new_project method of the flask api. """
        p_gga.return_value = True

        tests.create_projects(self.session)
        tests.create_projects_git(os.path.join(self.path, 'tickets'))
        tests.create_tokens(self.session)
        tests.create_tokens_acl(self.session)

        headers = {'Authorization': 'token foo_token'}

        # Invalid token
        output = self.app.post('/api/0/new', headers=headers)
        self.assertEqual(output.status_code, 401)
        data = json.loads(output.data)
        self.assertEqual(pagure.api.APIERROR.EINVALIDTOK.name,
                         data['error_code'])
        self.assertEqual(pagure.api.APIERROR.EINVALIDTOK.value, data['error'])

        headers = {'Authorization': 'token aaabbbcccddd'}

        # No input
        output = self.app.post('/api/0/new', headers=headers)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
              "error": "Invalid or incomplete input submited",
              "error_code": "EINVALIDREQ",
              "errors": {
                "name": ["This field is required."],
                "description": ["This field is required."]
              }
            }
        )

        data = {
            'name': 'test',
        }

        # Incomplete request
        output = self.app.post(
            '/api/0/new', data=data, headers=headers)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
              "error": "Invalid or incomplete input submited",
              "error_code": "EINVALIDREQ",
              "errors": {"description": ["This field is required."]}
            }
        )

        data = {
            'name': 'test',
            'description': 'Just a small test project',
        }

        # Valid request but repo already exists
        output = self.app.post(
            '/api/0/new/', data=data, headers=headers)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
                "error": "The project repo \"test\" already exists "
                    "in the database",
                "error_code": "ENOCODE"
            }
        )

        data = {
            'name': 'test_42',
            'description': 'Just another small test project',
        }

        # Valid request
        output = self.app.post(
            '/api/0/new/', data=data, headers=headers)
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {'message': 'Project "test_42" created'}
        )

    @patch.dict('pagure.APP.config', {'PRIVATE_PROJECTS': True})
    @patch('pagure.lib.git.generate_gitolite_acls')
    def test_api_new_project_private(self, p_gga):
        """ Test the api_new_project method of the flask api to create
        a private project. """
        p_gga.return_value = True

        tests.create_projects(self.session)
        tests.create_projects_git(os.path.join(self.path, 'tickets'))
        tests.create_tokens(self.session)
        tests.create_tokens_acl(self.session)

        headers = {'Authorization': 'token aaabbbcccddd'}

        data = {
            'name': 'test',
            'description': 'Just a small test project',
            'private': True,
        }

        # Valid request
        output = self.app.post(
            '/api/0/new/', data=data, headers=headers)
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {'message': 'Project "pingou/test" created'}
        )

    @patch('pagure.lib.git.generate_gitolite_acls')
    def test_api_new_project_user_token(self, p_gga):
        """ Test the api_new_project method of the flask api. """
        p_gga.return_value = True

        tests.create_projects(self.session)
        tests.create_projects_git(os.path.join(self.path, 'tickets'))
        tests.create_tokens(self.session, project_id=None)
        tests.create_tokens_acl(self.session)

        headers = {'Authorization': 'token foo_token'}

        # Invalid token
        output = self.app.post('/api/0/new', headers=headers)
        self.assertEqual(output.status_code, 401)
        data = json.loads(output.data)
        self.assertEqual(pagure.api.APIERROR.EINVALIDTOK.name,
                         data['error_code'])
        self.assertEqual(pagure.api.APIERROR.EINVALIDTOK.value, data['error'])

        headers = {'Authorization': 'token aaabbbcccddd'}

        # No input
        output = self.app.post('/api/0/new', headers=headers)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
              "error": "Invalid or incomplete input submited",
              "error_code": "EINVALIDREQ",
              "errors": {
                "name": ["This field is required."],
                "description": ["This field is required."]
              }
            }
        )

        data = {
            'name': 'test',
        }

        # Incomplete request
        output = self.app.post(
            '/api/0/new', data=data, headers=headers)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
              "error": "Invalid or incomplete input submited",
              "error_code": "EINVALIDREQ",
              "errors": {"description": ["This field is required."]}
            }
        )

        data = {
            'name': 'test',
            'description': 'Just a small test project',
        }

        # Valid request but repo already exists
        output = self.app.post(
            '/api/0/new/', data=data, headers=headers)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
                "error": "The project repo \"test\" already exists "
                    "in the database",
                "error_code": "ENOCODE"
            }
        )

        data = {
            'name': 'test_42',
            'description': 'Just another small test project',
        }

        # Valid request
        output = self.app.post(
            '/api/0/new/', data=data, headers=headers)
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {'message': 'Project "test_42" created'}
        )

        # Project with a namespace
        pagure.APP.config['ALLOWED_PREFIX'] = ['rpms']
        data = {
            'name': 'test_42',
            'namespace': 'pingou',
            'description': 'Just another small test project',
        }

        # Invalid namespace
        output = self.app.post(
            '/api/0/new/', data=data, headers=headers)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
                "error": "Invalid or incomplete input submited",
                "error_code": "EINVALIDREQ",
                "errors": {
                    "namespace": [
                        "Not a valid choice"
                    ]
                }
            }
        )

        data = {
            'name': 'test_42',
            'namespace': 'rpms',
            'description': 'Just another small test project',
        }

        # All good
        output = self.app.post(
            '/api/0/new/', data=data, headers=headers)
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {'message': 'Project "rpms/test_42" created'}
        )

    @patch('pagure.lib.git.generate_gitolite_acls')
    def test_api_new_project_user_ns(self, p_gga):
        """ Test the api_new_project method of the flask api. """
        pagure.APP.config['USER_NAMESPACE'] = True
        p_gga.return_value = True

        tests.create_projects(self.session)
        tests.create_projects_git(os.path.join(self.path, 'tickets'))
        tests.create_tokens(self.session)
        tests.create_tokens_acl(self.session)

        headers = {'Authorization': 'token aaabbbcccddd'}

        # Create a project with the user namespace feature on
        data = {
            'name': 'testproject',
            'description': 'Just another small test project',
        }

        # Valid request
        output = self.app.post(
            '/api/0/new/', data=data, headers=headers)
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {'message': 'Project "pingou/testproject" created'}
        )

        # Create a project with a namespace and the user namespace feature on
        pagure.APP.config['ALLOWED_PREFIX'] = ['testns']
        data = {
            'name': 'testproject2',
            'namespace': 'testns',
            'description': 'Just another small test project',
        }

        # Valid request
        output = self.app.post(
            '/api/0/new/', data=data, headers=headers)
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {'message': 'Project "testns/testproject2" created'}
        )

        pagure.APP.config['USER_NAMESPACE'] = False

    @patch('pagure.lib.git.generate_gitolite_acls')
    def test_api_fork_project(self, p_gga):
        """ Test the api_fork_project method of the flask api. """
        p_gga.return_value = True

        tests.create_projects(self.session)
        for folder in ['docs', 'tickets', 'requests', 'repos']:
            tests.create_projects_git(
                os.path.join(self.path, folder), bare=True)
        tests.create_tokens(self.session)
        tests.create_tokens_acl(self.session)

        headers = {'Authorization': 'token foo_token'}

        # Invalid token
        output = self.app.post('/api/0/fork', headers=headers)
        self.assertEqual(output.status_code, 401)
        data = json.loads(output.data)
        self.assertEqual(pagure.api.APIERROR.EINVALIDTOK.name,
                         data['error_code'])
        self.assertEqual(pagure.api.APIERROR.EINVALIDTOK.value, data['error'])

        headers = {'Authorization': 'token aaabbbcccddd'}

        # No input
        output = self.app.post('/api/0/fork', headers=headers)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
              "error": "Invalid or incomplete input submited",
              "error_code": "EINVALIDREQ",
              "errors": {"repo": ["This field is required."]}
            }
        )

        data = {
            'name': 'test',
        }

        # Incomplete request
        output = self.app.post(
            '/api/0/fork', data=data, headers=headers)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
              "error": "Invalid or incomplete input submited",
              "error_code": "EINVALIDREQ",
              "errors": {"repo": ["This field is required."]}
            }
        )

        data = {
            'repo': 'test',
        }

        # Valid request
        output = self.app.post(
            '/api/0/fork/', data=data, headers=headers)
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
                "message": "Repo \"test\" cloned to \"pingou/test\""
            }
        )

        data = {
            'repo': 'test',
        }

        # project already forked
        output = self.app.post(
            '/api/0/fork/', data=data, headers=headers)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
                "error": "Repo \"forks/pingou/test\" already exists",
                "error_code": "ENOCODE"
            }
        )

        data = {
            'repo': 'test',
            'username': 'pingou',
        }

        # Fork already exists
        output = self.app.post(
            '/api/0/fork/', data=data, headers=headers)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
                "error": "Repo \"forks/pingou/test\" already exists",
                "error_code": "ENOCODE"
            }
        )

        data = {
            'repo': 'test',
            'namespace': 'pingou',
        }

        # Repo does not exists
        output = self.app.post(
            '/api/0/fork/', data=data, headers=headers)
        self.assertEqual(output.status_code, 404)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
                "error": "Project not found",
                "error_code": "ENOPROJECT"
            }
        )

    @patch('pagure.lib.git.generate_gitolite_acls')
    def test_api_fork_project_user_token(self, p_gga):
        """ Test the api_fork_project method of the flask api. """
        p_gga.return_value = True

        tests.create_projects(self.session)
        for folder in ['docs', 'tickets', 'requests', 'repos']:
            tests.create_projects_git(
                os.path.join(self.path, folder), bare=True)
        tests.create_tokens(self.session, project_id=None)
        tests.create_tokens_acl(self.session)

        headers = {'Authorization': 'token foo_token'}

        # Invalid token
        output = self.app.post('/api/0/fork', headers=headers)
        self.assertEqual(output.status_code, 401)
        data = json.loads(output.data)
        self.assertEqual(pagure.api.APIERROR.EINVALIDTOK.name,
                         data['error_code'])
        self.assertEqual(pagure.api.APIERROR.EINVALIDTOK.value, data['error'])

        headers = {'Authorization': 'token aaabbbcccddd'}

        # No input
        output = self.app.post('/api/0/fork', headers=headers)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
              "error": "Invalid or incomplete input submited",
              "error_code": "EINVALIDREQ",
              "errors": {"repo": ["This field is required."]}
            }
        )

        data = {
            'name': 'test',
        }

        # Incomplete request
        output = self.app.post(
            '/api/0/fork', data=data, headers=headers)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
              "error": "Invalid or incomplete input submited",
              "error_code": "EINVALIDREQ",
              "errors": {"repo": ["This field is required."]}
            }
        )

        data = {
            'repo': 'test',
        }

        # Valid request
        output = self.app.post(
            '/api/0/fork/', data=data, headers=headers)
        self.assertEqual(output.status_code, 200)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
                "message": "Repo \"test\" cloned to \"pingou/test\""
            }
        )

        data = {
            'repo': 'test',
        }

        # project already forked
        output = self.app.post(
            '/api/0/fork/', data=data, headers=headers)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
                "error": "Repo \"forks/pingou/test\" already exists",
                "error_code": "ENOCODE"
            }
        )

        data = {
            'repo': 'test',
            'username': 'pingou',
        }

        # Fork already exists
        output = self.app.post(
            '/api/0/fork/', data=data, headers=headers)
        self.assertEqual(output.status_code, 400)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
                "error": "Repo \"forks/pingou/test\" already exists",
                "error_code": "ENOCODE"
            }
        )

        data = {
            'repo': 'test',
            'namespace': 'pingou',
        }

        # Repo does not exists
        output = self.app.post(
            '/api/0/fork/', data=data, headers=headers)
        self.assertEqual(output.status_code, 404)
        data = json.loads(output.data)
        self.assertDictEqual(
            data,
            {
                "error": "Project not found",
                "error_code": "ENOPROJECT"
            }
        )

if __name__ == '__main__':
    unittest.main(verbosity=2)
