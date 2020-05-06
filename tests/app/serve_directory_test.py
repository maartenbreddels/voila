# test serving a notebook or python/c++ notebook
import os
import pytest

TEST_XEUS_CLING = os.environ.get('VOILA_TEST_XEUS_CLING', '') == '1'


@pytest.fixture
def voila_args(notebook_directory, voila_args_extra):
    return ['--Voila.root_dir=%r' % notebook_directory, '--Voila.log_level=DEBUG'] + voila_args_extra + ['--no-browser']


async def test_print(fetch):
    response = await fetch('voila', 'render', 'print.ipynb', method='GET')
    assert response.code == 200
    assert 'Hi Voila' in response.body.decode('utf-8')


@pytest.fixture
def voila_args_extra():
    return ['--Voila.extension_language_mapping={".py": "python"}']


async def test_print_py(fetch):
    response = await fetch('voila', 'render', 'print.py', method='GET')
    assert response.code == 200
    assert 'Hi Voila' in response.body.decode('utf-8')


@pytest.mark.skipif(not TEST_XEUS_CLING, reason='opt in to avoid having to install xeus-cling')
async def test_print_cpp_notebook(fetch):
    response = await fetch('voila', 'render', 'print_cpp.ipynb', method='GET')
    assert response.code == 200
    assert 'Hi Voila, from c++' in response.body.decode('utf-8')
