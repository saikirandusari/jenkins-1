#!/bin/env python
"""test_automation_options.py - Tests module for automation_options.py"""

try:
    import pytest
    from unittest.mock import MagicMock, sentinel
except ImportError:
    from mock import MagicMock, sentinel
from scripts.stdci_dsl.options.globals import _get_global_options
from scripts.stdci_dsl.options.parser_utils import get_merged_options
from scripts.stdci_dsl.options.defaults import apply_default_options
from scripts.stdci_dsl.options.defaults.values import DefaultValue
from scripts.stdci_dsl.job_thread import JobThread
from scripts.stdci_dsl.options.normalize import (
    _render_template, _resolve_stdci_yaml_config, _resolve_stdci_list_config,
    _resolve_stdci_script, _normalize_repos_config, _normalize_mounts_config,
    RepoConfig, MountConfig, _resolve_changed_files,
    _resolve_stdci_runif_conditions, ConfigurationSyntaxError
)


@pytest.fixture(scope='function')
def stdci_project_dir(tmpdir):
    project_dir = tmpdir.mkdir('stdci-project')
    automation = project_dir.mkdir('automation')
    (automation/'check-patch.environment.yaml').write('test: yaml cfg\n')
    (automation/'check-patch.sh').write('script')
    (automation/'check-patch.packages').write('p1\np2')
    (automation/'check-patch.yumrepos').write('yumreposfile')
    (automation/'check-merged.sh').mksymlinkto('check-patch.sh')
    return project_dir


@pytest.mark.parametrize(
    "thread,expected",
    [
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64', {
                'mounts': [
                    'mymount1:mymountdst1',
                    'mymount2:mymountdst2',
                    'mymountdst3'
                ],
            }),
            [
                MountConfig(src='mymount1', dst='mymountdst1'),
                MountConfig(src='mymount2', dst='mymountdst2'),
                MountConfig(src='mymountdst3', dst='mymountdst3')
            ]
        ),
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64', {
                'mounts': ['mount1', 'mount2', 'mount3'],
            }),
            [
                MountConfig(src='mount1', dst='mount1'),
                MountConfig(src='mount2', dst='mount2'),
                MountConfig(src='mount3', dst='mount3')
            ]
        ),
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64', {'mounts': []}),
            []
        )
    ]
)
def test_normalize_mounts_config(thread, expected, stdci_project_dir):
    res = _normalize_mounts_config(str(stdci_project_dir), thread)
    assert res == expected


@pytest.mark.parametrize(
    "thread,expected",
    [
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64', {
                'repos': [
                    'myrepo1,myrepourl1',
                    'myrepo2,myrepourl2',
                    'myrepourl3'
                ],
            }),
            [
                RepoConfig('myrepo1', 'myrepourl1'),
                RepoConfig('myrepo2', 'myrepourl2'),
                RepoConfig('repo-4639b47b04736088069cc6cc98b9e869', 'myrepourl3')
            ]
        ),
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64', {
                'repos': [
                    'repourl1',
                    'repourl2',
                    'repourl3'
                ],
            }),
            [
                RepoConfig('repo-6ecbe834dc314939f1f07626c20171a7', 'repourl1'),
                RepoConfig('repo-8d0c508dc795956e772ab3d1e37d0195', 'repourl2'),
                RepoConfig('repo-c1f2a55f1eacefc4c42429033b723cb8', 'repourl3')
            ]
        ),
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64', {'repos': []}),
            []
        )
    ]
)
def test_normalize_repos_config(thread, expected, stdci_project_dir):
    res = _normalize_repos_config(str(stdci_project_dir), thread)
    assert res == expected


@pytest.mark.parametrize(
    "thread,templates,expected",
    [
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64', {}),
            '{{ stage }}.{{ substage }}.{{ distro }}.{{ arch }}',
            'check-patch.default.el7.x86_64'
        )
    ]
)
def test_render_template(thread, templates, expected):
    out = _render_template(thread, templates)
    assert out == expected


@pytest.mark.parametrize(
    "options,expected",
    [
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64',
                {
                    'script':
                    {
                        'fromfile': 'automation/check-patch.sh'
                    },
                    'ignore_if_missing_script': False
                },
            ),
            'automation/check-patch.sh'
        ),
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64',
                {
                    'script':
                    {
                        'fromfile':
                        [
                            'no',
                            'no',
                            'check-patch.sh',
                            'no'
                        ]
                    },
                    'ignore_if_missing_script': False,
                    'scriptsdirectory': 'automation'
                },
            ),
            'automation/check-patch.sh'
        ),
        (
            JobThread('check-merged', 'default', 'el7', 'x86_64',
                {
                    'script':
                    {
                        'fromfile':
                        [
                            'no',
                            'no',
                            'check-merged.sh',
                            'no'
                        ]
                    },
                    'ignore_if_missing_script': False,
                    'scriptsdirectory': 'automation'
                },
            ),
            'automation/check-merged.sh'
        ),
    ]
)
def test_resolve_stdci_script(options, expected, stdci_project_dir):
    out = _resolve_stdci_script(stdci_project_dir, options)
    ex = expected
    assert out == ex


@pytest.mark.parametrize(
    "options,expected",
    [
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64',
                {
                    'packages':
                    {
                        'fromlistfile': 'automation/check-patch.packages'
                    },
                },
            ),
            ['p1', 'p2']
        ),
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64',
                {
                    'packages':
                    {
                        DefaultValue: True,
                        'fromlistfile': 'NotFound'
                    },
                },
            ),
            []
        ),
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64',
                {
                    'packages':
                    {
                        'fromlistfile': 'check-patch.packages'
                    },
                    'scriptsdirectory': 'automation'
                },
            ),
            ['p1', 'p2']
        )
    ]
)
def test_resolve_stdci_list_config(options, expected, stdci_project_dir):
    assert _resolve_stdci_list_config(
        stdci_project_dir, options, 'packages'
    ) == expected


@pytest.mark.parametrize(
    "options,expected",
    [
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64',
                {
                    'environment':
                    {
                        'fromfile': 'automation/check-patch.environment.yaml'
                    },
                },
            ),
            {'test': 'yaml cfg'}
        ),
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64',
                {
                    'environment':
                    {
                        DefaultValue: True,
                        'fromfile': 'NotFound'
                    },
                },
            ),
            {}
        ),
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64',
                {
                    'environment':
                    {
                        'fromfile': 'check-patch.environment.yaml'
                    },
                    'scriptsdirectory': 'automation'
                },
            ),
            {'test': 'yaml cfg'}
        ),
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64',
                {
                    'environment': 'inline specified'
                },
            ),
            'inline specified'
        ),
        (
            JobThread('check-patch', 'default', 'el7', 'x86_64',
                {
                    'environment': ['inline', 'specified']
                },
            ),
            ['inline', 'specified']
        )
    ]
)
def test_resolve_stdci_yaml_config(options, expected, stdci_project_dir):
    assert _resolve_stdci_yaml_config(
        stdci_project_dir, options, 'environment'
    ) == expected


@pytest.mark.parametrize(
    "options1,options2,expected",
    [
        (
            {'packages': ['p1', 'p2', 'p3']},
            {'packages': ['p4']},
            {'packages': ['p4']},
        ),
        (
            {'packages': ['p1']},
            {'repos': ['r1']},
            {'packages': ['p1'], 'repos': ['r1']}
        ),
        (
            {'repos': ['r1'], 'releasebranches': ['master', 'test']},
            {'repos': ['r2'], 'releasebranches': ['4.1']},
            {'repos': ['r2'], 'releasebranches': ['4.1']}
        ),
        (
            {'releasebranches': 'br1', 'runtime_req': 'rq1'},
            {'repos': 'r1'},
            {'releasebranches': 'br1', 'runtime_req': 'rq1', 'repos': 'r1'}
        ),
        (
            {'releasebranches': 'br1', 'runtime_req': 'rq1'},
            {'releasebranches': 'br2', 'runtime_req': 'rq2'},
            {'releasebranches': 'br2', 'runtime_req': 'rq2'},
        )
    ]
)
def test_get_merged_options(options1, options2, expected):
    assert get_merged_options(options1, options2) == expected


@pytest.mark.parametrize(
    "threads,expected",
    [
        (
            [
                JobThread(
                    None, 'custom', None, None,
                    {
                        'mounts': {'fromfile': 'path_to_file'},
                        'scriptsdirectory': 'myCustomDir',
                        'packages': {'fromfile': ['f1', 'f2']},
                        'repos': ['r1', 'r2'],
                        'environment': {'some env req': 123},
                    }
                ),
            ],
            [
                JobThread(None, 'custom', None, None,
                    {
                        'scriptsdirectory': 'myCustomDir',
                        'yumrepos':
                        {
                            DefaultValue: True,
                            'fromfile':
                            [
                                '{{ stage }}.{{ substage }}.yumrepos.{{ distro }}.{{ arch }}',
                                '{{ stage }}.{{ substage }}.yumrepos.{{ distro }}',
                                '{{ stage }}.{{ substage }}.yumrepos.{{ arch }}',
                                '{{ stage }}.{{ substage }}.yumrepos',
                            ]
                        },
                        'script':
                        {
                            DefaultValue: True,
                            'fromfile':
                            [
                                '{{ stage }}.{{ substage }}.sh.{{ distro }}.{{ arch }}',
                                '{{ stage }}.{{ substage }}.sh.{{ distro }}',
                                '{{ stage }}.{{ substage }}.sh.{{ arch }}',
                                '{{ stage }}.{{ substage }}.sh',
                            ]
                        },
                        'upstreamsources': {},
                        'repos': ['r1', 'r2'],
                        'environment': {'some env req': 123},
                        'runtimerequirements': {},
                        'mounts': {'fromfile': 'path_to_file'},
                        'releasebranches': {},
                        'packages': {'fromfile': ['f1', 'f2']},
                        'ignore_if_missing_script': True}
                    )
                ],
        ),
        (
            [
                JobThread(
                    None, 'default', None, None,
                    {
                        'mounts': {'fromfile': 'path_to_file'},
                        'scriptsdirectory': 'myCustomDir',
                        'packages': {'fromfile': ['f1', 'f2']},
                        'repos': ['r1', 'r2'],
                        'environment': {'some env req': 123},
                    }
                ),
            ],
            [
                JobThread(None, 'default', None, None,
                    {
                        'scriptsdirectory': 'myCustomDir',
                        'yumrepos':
                        {
                            DefaultValue: True,
                            'fromfile':
                            [
                                '{{ stage }}.{{ substage }}.yumrepos.{{ distro }}.{{ arch }}',
                                '{{ stage }}.{{ substage }}.yumrepos.{{ distro }}',
                                '{{ stage }}.{{ substage }}.yumrepos.{{ arch }}',
                                '{{ stage }}.{{ substage }}.yumrepos',
                                '{{ stage }}.yumrepos.{{ distro }}.{{ arch }}',
                                '{{ stage }}.yumrepos.{{ distro }}',
                                '{{ stage }}.yumrepos.{{ arch }}',
                                '{{ stage }}.yumrepos'
                            ]
                        },
                        'script':
                        {
                            DefaultValue: True,
                            'fromfile':
                            [
                                '{{ stage }}.{{ substage }}.sh.{{ distro }}.{{ arch }}',
                                '{{ stage }}.{{ substage }}.sh.{{ distro }}',
                                '{{ stage }}.{{ substage }}.sh.{{ arch }}',
                                '{{ stage }}.{{ substage }}.sh',
                                '{{ stage }}.sh.{{ distro }}.{{ arch }}',
                                '{{ stage }}.sh.{{ distro }}',
                                '{{ stage }}.sh.{{ arch }}',
                                '{{ stage }}.sh'
                            ]
                        },
                        'upstreamsources': {},
                        'repos': ['r1', 'r2'],
                        'environment': {'some env req': 123},
                        'runtimerequirements': {},
                        'mounts': {'fromfile': 'path_to_file'},
                        'releasebranches': {},
                        'packages': {'fromfile': ['f1', 'f2']},
                        'ignore_if_missing_script': True
                    }
               )
            ],
        ),
        (
            [
                JobThread(
                    None, 'default', None, None,
                    {
                        'mounts': {'fromfile': 'path_to_file'},
                        'scriptsdirectory': 'myCustomDir',
                        'packages': {'fromfile': ['f1', 'f2']},
                        'repos': ['r1', 'r2'],
                        'environment': {'some env req': 123},
                        'script': 'specified inline',
                        'yumrepos': ['y1', 'y2'],
                    }
                ),
            ],
            [
                JobThread(
                    None, 'default', None, None,
                    {
                        'scriptsdirectory': 'myCustomDir',
                        'yumrepos': ['y1', 'y2'],
                        'script': 'specified inline',
                        'upstreamsources': {},
                        'repos': ['r1', 'r2'],
                        'environment': {'some env req': 123},
                        'runtimerequirements': {},
                        'mounts': {'fromfile': 'path_to_file'},
                        'releasebranches': {},
                        'packages': {'fromfile': ['f1', 'f2']},
                        'ignore_if_missing_script': False
                    }
                )
            ]
        ),
    ]
)
def test_apply_default_options(threads, expected):
    assert list(apply_default_options(threads)) == expected


@pytest.mark.parametrize(
    "threads,expected",
    [
        (
            [
                JobThread('a', 'b', 'c', 'd', {'p': 'p'}),
                JobThread('c', 'd', 'c', 'd', {'releasebranches': 'master'})
            ],
            {'releasebranches': 'master'}
        ),
        (
            [
                JobThread('a', 'b', 'c', 'd', {'p': 'p'}),
                JobThread('c', 'd', 'c', 'd', {'upstreamsources': 'usrc'})
            ],
            {'upstreamsources': 'usrc'}
        ),
        (
            [
                JobThread('a', 'b', 'c', 'd', {'p': 'p'}),
                JobThread('c', 'd', 'c', 'd', {'runtimerequirements': 'rtr'})
            ],
            {}
        ),
        (
            [
                JobThread('a', 'b', 'c', 'd', {'p': 'p'}),
                JobThread('c', 'd', 'c', 'd', {'e': 'e'})
            ],
            {}
        ),
        (
            [
                JobThread(
                    'a', 'b', 'c', 'd',
                    {'runtimerequirements': 'rtr', 'upstreamsources': 'usrc'},
                ),
                JobThread('c', 'd', 'c', 'd', {'releasebranches': 'rbrnch'})
            ],
            {
                'releasebranches': 'rbrnch',
                'upstreamsources': 'usrc'
            }
        ),
    ]
)
def test_get_global_options_cfg(threads, expected):
    assert _get_global_options(threads) == expected


@pytest.mark.parametrize(
    "modified,conditions,expected",
    [
        (
            ['some-file-1', 'some-file-2', 'some-file-3'],
            ['some-*-2'],
            True
        ),
        (
            ['some-file-1', 'some-file-2', 'some-file-3'],
            ['some-*-4'],
            False
        ),
        (
            ['some-file-1', 'some-file-2', 'some-file-3'],
            ['some-file-3'],
            True
        ),
        (
            ['a'],
            ['{{ stage }}'],
            True
        ),
        (
            ['something', 'b', 'something-else'],
            ['{{ substage }}'],
            True
        ),
        (
            ['something', 'something-else'],
            ['{{ substage }}'],
            False
        ),
        (
            ['file'],
            [],
            False
        ),
        (
            [],
            ['condition'],
            False
        ),
        (
            [],
            [],
            False
        ),
    ]
)
def test_resolve_changed_files(modified, conditions, expected, monkeypatch):
    monkeypatch.setattr(
        'scripts.stdci_dsl.options.normalize.MODIFIED_FILES',
        {'project': modified},
    )
    thread = JobThread('a', 'b', 'c', 'd', {})
    out = _resolve_changed_files('project', thread, conditions)
    assert out == expected


@pytest.mark.parametrize(
    "thread,modified_files,expected",
    [
        (
            JobThread('a', 'b', 'c', 'd',
                {'not': {'filechanged': ['file-*']}},
            ),
            ['file-1'],
            False
        ),
        (
            JobThread('a', 'b', 'c', 'd',
                {'not': {'filechanged': ['file-*']}},
            ),
            ['something'],
            True
        ),
        (
            JobThread('a', 'b', 'c', 'd',
                {'all': [{'filechanged': ['file-*']}]},
            ),
            ['file-1'],
            True
        ),
        (
            JobThread('a', 'b', 'c', 'd',
                {'all': [
                        {'filechanged': ['file-*']},
                        {'filechanged': ['other-file*']}
                    ]
                },
            ),
            ['file-1'],
            False
        ),
        (
            JobThread('a', 'b', 'c', 'd',
                {
                    'all': [
                        {
                            'all':
                            [
                                {'filechanged': ['file1']},
                                {'filechanged': ['file2']}
                            ]
                        },
                        {
                            'any':
                            [
                                {'filechanged': ['file2']},
                                {'filechanged': ['file3']}
                            ]
                        }
                    ]
                },
            ),
            ['file2'],
            False
        ),
        (
            JobThread('a', 'b', 'c', 'd',
                {
                    'all': [
                        {
                            'all':
                            [
                                {'filechanged': ['file1']},
                                {'filechanged': ['file2']}
                            ]
                        },
                        {
                            'any':
                            [
                                {'filechanged': ['file2']},
                                {'filechanged': ['file3']}
                            ]
                        }
                    ]
                },
            ),
            ['file1', 'file2'],
            True
        ),
        (
            JobThread('a', 'b', 'c', 'd',
                {
                    'any': [
                        {
                            'all':
                            [
                                {'filechanged': ['file1']},
                                {'filechanged': ['file2']}
                            ]
                        },
                        {
                            'any':
                            [
                                {'filechanged': ['file2']},
                                {'filechanged': ['file3']}
                            ]
                        }
                    ]
                },
            ),
            ['file1', 'file2'],
            True
        ),
        (
            JobThread('a', 'b', 'c', 'd',
                {'any': [
                    {'all': [
                        {'filechanged': 'file1'},
                        {'filechanged': 'file2'},
                        {'any': [
                            {'filechanged': 'file2'},
                            {'filechanged': 'file4'}]}
                    ]},
                    {'any': [
                        {'filechanged': 'file5'},
                        {'filechanged': 'file6'}
                    ]}
                ],
                'filechanged': 'file2',
                },
            ),
            ['file1', 'file2', 'file4', 'file5', 'file6'],
            True
        ),
        (
            JobThread('a', 'b', 'c', 'd',
                {'any': [
                    {
                        'all': [
                            {'filechanged': 'file1'},
                            {'filechanged': 'file2'},
                            {'any': [
                                {'filechanged': 'file2'},
                                {'filechanged': 'file4'}]
                            }
                        ]
                    },
                    {'any': [
                        {'filechanged': 'file5'},
                        {'filechanged': 'file6'}]
                    }
                ],
                'filechanged': 'file2'
                },
            ),
            ['file3'],
            False
        ),
        (
            JobThread('a', 'b', 'c', 'd',
                {'not':
                    {
                        'all': [
                            {'filechanged': 'file1'},
                            {'filechanged': 'file2'},
                            {'any': [
                                {'filechanged': 'file3'},
                                {'filechanged': 'file4'}]
                            }
                        ]
                    },
                }
            ),
            ['file1', 'file2', 'file3'],
            False
        ),
        (
            JobThread('a', 'b', 'c', 'd',
                {
                    'all': [
                        {'filechanged': 'file1'},
                        {'filechanged': 'file2'},
                        {'any': [
                            {'filechanged': 'file3'},
                            {'filechanged': 'file4'}]
                        }
                    ]
                },
            ),
            ['file1', 'file2', 'file3'],
            True
        ),
        (
            JobThread('a', 'b', 'c', 'd',
                {
                    'all': [
                        {'filechanged': 'file1'},
                        {'filechanged': 'file2'},
                        {'any': [
                            {'filechanged': 'file3'},
                            {'filechanged': 'file4'}]
                        }
                    ]
                },
            ),
            ['file1', 'file2'],
            False
        ),
        (
            JobThread('a', 'b', 'c', 'd',
                {'not':
                    {'all': [
                        {
                            'all': [
                                {'filechanged': 'file1'},
                                {'filechanged': 'file2'},
                                {'any': [
                                    {'filechanged': 'file3'},
                                    {'filechanged': 'file4'}]
                                }
                            ]
                        },
                        {'any': [
                            {'filechanged': 'file5'},
                            {'filechanged': 'file6'}]
                        }
                    ],
                    'filechanged': 'file2'
                    },
                }
            ),
            ['file1'],
            True
        ),
        (
            JobThread('a', 'b', 'c', 'd',
                {'all': [
                    {
                        'all': [
                            {'filechanged': 'file1'},
                            {'filechanged': 'file2'},
                            {'any': [
                                {'filechanged': 'file3'},
                                {'filechanged': 'file4'}]
                            }
                        ]
                    },
                    {'any': [
                        {'filechanged': 'file5'},
                        {'filechanged': 'file6'}]
                    }
                ],
                'filechanged': 'file2'
                },
            ),
            ['file1'],
            False
        ),
        (
            JobThread('a', 'b', 'c', 'd',
                {'all': [
                    {'all': [
                        {'filechanged': 'file1'},
                        {'filechanged': 'file2'},
                        {'any': [
                            {'filechanged': 'file3'},
                            {'filechanged': 'file4'}]
                        }]
                    },
                    {'any': [
                        {'filechanged': 'file5'},
                        {'filechanged': 'file6'}]
                    }
                ],
                'filechanged': 'file2'
                },
            ),
            ['file1', 'file2', 'file3', 'file5'],
            True
        ),
        (
            JobThread('a', 'b', 'c', 'd',
                {'not':
                    {'all': [
                        {'all': [
                            {'filechanged': 'file1'},
                            {'filechanged': 'file2'},
                            {'any': [
                                {'filechanged': 'file3'},
                                {'filechanged': 'file4'}]
                            }]
                        },
                        {'any': [
                            {'filechanged': 'file5'},
                            {'filechanged': 'file6'}]
                        }
                    ],
                    'filechanged': 'file2'
                    },
                }
            ),
            ['file1', 'file2', 'file3', 'file5'],
            False
        ),
        (
            JobThread('a', 'b', 'c', 'd', {'all': []},),
            ['file1', 'file2'],
            True
        ),
        (
            JobThread('a', 'b', 'c', 'd', {'any': []},),
            ['file1', 'file2'],
            False
        ),
    ]
)
def test_resolve_stdci_runif_conditions(
    thread, modified_files, expected, monkeypatch
):
    monkeypatch.setattr(
        'scripts.stdci_dsl.options.normalize.MODIFIED_FILES',
        {'project': modified_files}
    )
    out = _resolve_stdci_runif_conditions('project', thread, thread.options)
    assert out == expected


@pytest.mark.parametrize(
    "conditions",
    [
        {'a': 'b'},
        1,
        [{'file': 'abc'}],
    ]
)
def test_resolve_changed_files_exceptions(conditions, monkeypatch):
    monkeypatch.setattr(
        'scripts.stdci_dsl.options.normalize.MODIFIED_FILES',
        {'project': []}
    )
    thread = JobThread('a', 'b', 'c', 'd', {})
    with pytest.raises(ConfigurationSyntaxError):
        _resolve_changed_files('project', thread, conditions)
