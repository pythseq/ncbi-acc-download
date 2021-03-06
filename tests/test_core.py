"""Tests for the core module."""

from argparse import Namespace
from io import StringIO
import pytest
import requests
import requests_mock

from ncbi_acc_download import core


@pytest.yield_fixture
def req():
    """Get requests_mock into the pytest infrastructure."""
    with requests_mock.mock() as req:
        yield req


def test_config():
    """Test the config class."""
    args = Namespace(molecule="nucleotide", verbose=False)
    config = core.Config.from_args(args)
    assert config.verbose is False
    assert config.molecule == 'nucleotide'
    assert config.extended_validation == 'none'

    args = Namespace(molecule="protein", verbose=True)
    config = core.Config.from_args(args)
    assert config.verbose is True
    assert config.molecule == 'protein'


def test_config_no_biopython(monkeypatch):
    """Test the correct errors are raised if Biopython is not available."""
    monkeypatch.setattr(core, 'HAVE_BIOPYTHON', False)
    assert core.HAVE_BIOPYTHON is False
    args = Namespace(extended_validation='all')
    with pytest.raises(ValueError):
        core.Config.from_args(args)


def test_config_have_biopython():
    """Test we detect Biopython."""
    assert core.HAVE_BIOPYTHON
    args = Namespace(extended_validation='all')
    config = core.Config.from_args(args)
    assert config.extended_validation == 'all'


def test_download_to_file(req, tmpdir):
    """Test downloading things from NCBI."""
    req.get(core.NCBI_URL, text='This works.')
    outdir = tmpdir.mkdir('outdir')
    filename = outdir.join('foo')
    expected = outdir.join('foo.gbk')
    config = core.Config(molecule='nucleotide', verbose=False)

    core.download_to_file('FOO', config, filename=filename)

    assert expected.check()


def test_build_params():
    """Test we build the right set of parameters."""
    config = core.Config(molecule='nucleotide', verbose=False)
    dl_id = 'TEST'
    expected_params = {
        'tool': 'ncbi-acc-download',
        'retmode': 'text',
        'rettype': 'gbwithparts',
        'id': 'TEST',
        'db': 'nucleotide'
    }

    params = core.build_params(dl_id, config)

    assert params == expected_params

    expected_params = {
        'tool': 'ncbi-acc-download',
        'retmode': 'text',
        'rettype': 'fasta',
        'id': 'TEST',
        'db': 'protein'
    }
    config.molecule = 'protein'

    params = core.build_params(dl_id, config)

    assert params == expected_params


def test_generate_filename():
    """Test output file name generation."""
    params = dict(id='TEST', db='nucleotide')

    filename = core._generate_filename(params, 'foo')
    assert filename == 'foo.gbk'

    params['db'] = 'protein'
    filename = core._generate_filename(params, None)
    assert filename == 'TEST.fa'


def test_validate_and_write_error_pattern_raises(req):
    """Test scanning the download file for error patterns."""
    handle = StringIO()
    req.get('http://fake/', text=u'ID list is empty')
    r = requests.get('http://fake/')
    config = core.Config()

    with pytest.raises(core.BadPatternError):
        core._validate_and_write(r, handle, 'FAKE', config)


def test_validate_and_write_emit(req):
    """Test writing prints dots in verbose mode."""
    handle = StringIO()
    req.get('http://fake/', text=u'This is a sequence file, honest.')
    r = requests.get('http://fake/')
    output = StringIO()
    config = core.Config()
    config.emit = output.write
    core._validate_and_write(r, handle, 'FAKE', config)

    assert output.getvalue() == u'.\n'
    assert handle.getvalue() == u'This is a sequence file, honest.'


def test_validate_and_write_extended_validation(req):
    """Test extended validation before writing."""
    handle = StringIO()
    req.get('http://fake/', text=u'>foo\nMAGIC')
    r = requests.get('http://fake/')
    config = core.Config(extended_validation='loads', molecule='protein')
    core._validate_and_write(r, handle, 'FAKE', config)

    assert handle.getvalue() == u'>foo\nMAGIC'


def test_get_stream_exception(req):
    """Test getting a download stream handles exceptions."""
    req.get(core.NCBI_URL, exc=requests.exceptions.RequestException)
    params = dict(id='FAKE')
    with pytest.raises(core.DownloadError):
        core.get_stream(params)


def test_get_stream_bad_status(req):
    """Test getting a download stream handles bad status codes."""
    req.get(core.NCBI_URL, text=u'Nope!', status_code=404)
    params = dict(id='FAKE')
    with pytest.raises(core.DownloadError):
        core.get_stream(params)
