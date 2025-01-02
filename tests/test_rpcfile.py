"""Verify implementation of RPC file helpers."""

import collections.abc
import datetime
import pathlib
import typing

import pytest

from shv import (
    FileProviderRW,
    RpcFile,
    RpcFileStat,
    RpcMethodAccess,
    RpcMethodDesc,
    RpcMethodFlags,
    SHVBase,
    SHVClient,
    SHVType,
)


class FilesProvider(SHVClient):
    APP_NAME = "testdev"

    def __init__(
        self,
        *args: typing.Any,  # noqa ANNN401
        path: pathlib.Path,
        **kwargs: typing.Any,  # noqa ANNN401
    ) -> None:
        self.path = path
        super().__init__(*args, **kwargs)  # notype

    def _ls(self, path: str) -> collections.abc.Iterator[str]:
        yield from super()._ls(path)
        if not path:
            yield "files"
        elif path == "files" or path.startswith("files/"):
            pth = self.path / path[6:]
            if pth.is_dir():
                for spth in pth.iterdir():
                    yield spth.name

    def _dir(self, path: str) -> collections.abc.Iterator[RpcMethodDesc]:
        yield from super()._dir(path)
        if path.startswith("files/"):
            pth = self.path / path[6:]
            if pth.is_file():
                yield from FileProviderRW.dir()

    async def _method_call(self, request: SHVBase.Request) -> SHVType:
        if request.path.startswith("files/"):
            pth = self.path / request.path[6:]
            if pth.is_file():
                try:
                    # TODO use also other providers
                    return FileProviderRW.method_call(
                        pth, request.method, request.param, request.access
                    )
                except NotImplementedError:
                    pass
        return await super()._method_call(request)


@pytest.fixture(name="device")
async def fixture_device(shvbroker, url_test_device, tmp_path):
    """Run FilesProvider and provide instance to access it."""
    device = await FilesProvider.connect(url_test_device, path=tmp_path)
    yield device
    await device.disconnect()


@pytest.fixture(name="seed_tmp")
def fixture_seed_tmp(tmp_path):
    """Create some dummy files in tmp_path."""
    (tmp_path / "bin").write_bytes(b"abc")
    (tmp_path / "lorem.txt").write_text(
        "Lorem ipsum dolor sit amet, consectetur adipiscing elit, sed do eiusmod tempor incididunt ut labore et dolore magna aliqua."
    )
    (tmp_path / "sub" / "subsub").mkdir(parents=True)


@pytest.mark.parametrize(
    "path,res",
    (
        ("test/device", [".app", "files"]),
        ("test/device/files", ["bin", "lorem.txt", "sub"]),
        ("test/device/files/bin", []),
        ("test/device/files/lorem.txt", []),
        ("test/device/files/sub", ["subsub"]),
        ("test/device/files/sub/subsub", []),
    ),
)
async def test_ls(client, device, seed_tmp, path, res):
    assert await client.ls(path) == res


@pytest.mark.parametrize(
    "path,res",
    (
        (
            "test/device/files/lorem.txt",
            [
                RpcMethodDesc.stddir(),
                RpcMethodDesc.stdls(),
                RpcMethodDesc.getter("stat", "Null", "ofstat", RpcMethodAccess.READ),
                RpcMethodDesc.getter("size", "Null", "Int", RpcMethodAccess.READ),
                RpcMethodDesc(
                    "crc", param="ifcrc", result="UInt", access=RpcMethodAccess.READ
                ),
                RpcMethodDesc(
                    "sha1", param="ifsha1", result="Bytes", access=RpcMethodAccess.READ
                ),
                RpcMethodDesc(
                    "read",
                    RpcMethodFlags.LARGE_RESULT_HINT,
                    "ifread",
                    "Bytes",
                    RpcMethodAccess.READ,
                ),
                RpcMethodDesc(
                    "write",
                    param="ifwrite",
                    result="Null",
                    access=RpcMethodAccess.WRITE,
                ),
                RpcMethodDesc(
                    "truncate", param="Int", result="Null", access=RpcMethodAccess.WRITE
                ),
                RpcMethodDesc(
                    "append", param="Bytes", result="Null", access=RpcMethodAccess.WRITE
                ),
            ],
        ),
    ),
)
async def test_dir(client, device, seed_tmp, path, res):
    assert await client.dir(path) == res


@pytest.fixture(name="file_bin")
def fixture_file_bin(client, device, seed_tmp):
    return RpcFile(client, "test/device/files/bin", RpcFile.Flag(0))


def test_file_bin_path(file_bin):
    assert file_bin.path == "test/device/files/bin"


async def test_file_bin_readable(file_bin):
    assert await file_bin.readable()


async def test_file_bin_writable(file_bin):
    assert await file_bin.writable()


async def test_file_bin_resizable(file_bin):
    assert await file_bin.resizable()


async def test_file_bin_stat(file_bin, tmp_path):
    stat = (tmp_path / "bin").stat()
    access = datetime.datetime.fromtimestamp(stat.st_atime, tz=datetime.UTC)
    access = access.replace(microsecond=(access.microsecond // 1000) * 1000)
    mod = datetime.datetime.fromtimestamp(stat.st_mtime, tz=datetime.UTC)
    mod = access.replace(microsecond=(mod.microsecond // 1000) * 1000)
    assert await file_bin.stat() == RpcFileStat(
        stat.st_size, stat.st_blksize, access, mod
    )


async def test_file_bin_size(client, device, seed_tmp):
    assert await client.call("test/device/files/bin", "size") == 3


@pytest.mark.parametrize(
    "offset,size,res",
    (
        (0, None, 891568578),
        (1, None, 3265866552),
        (0, 1, 3904355907),
    ),
)
async def test_file_bin_crc32(file_bin, offset, size, res):
    assert await file_bin.crc32(offset, size) == res


@pytest.mark.parametrize(
    "offset,size,res",
    (
        (0, None, b"\xa9\x99>6G\x06\x81j\xba>%qxP\xc2l\x9c\xd0\xd8\x9d"),
        (1, None, b"[%\x05\x03\x9a\xc5\xaf\x9e\x19\x7f]\xad\x04\x119\x06\xa9\xcf\x9a*"),
        (0, 1, b"\x86\xf7\xe47\xfa\xa5\xa7\xfc\xe1]\x1d\xdc\xb9\xea\xea\xea7vg\xb8"),
    ),
)
async def test_file_bin_sha1(file_bin, offset, size, res):
    assert await file_bin.sha1(offset, size) == res


async def test_file_bin_read(file_bin):
    assert file_bin.offset == 0
    assert await file_bin.read() == b"abc"
    assert file_bin.offset == 3


async def test_file_bin_read_short(file_bin):
    assert file_bin.offset == 0
    assert await file_bin.read(2) == b"ab"
    assert file_bin.offset == 2
    assert await file_bin.read(2) == b"c"
    assert file_bin.offset == 3


async def test_file_bin_write(file_bin, tmp_path):
    file_bin.offset = 3
    await file_bin.write(b"def")
    assert file_bin.offset == 6
    with (tmp_path / "bin").open("rb") as file:
        assert file.read() == b"abcdef"


async def test_file_bin_flush(file_bin, tmp_path):
    # This does nothing so just call it that it won't fail
    await file_bin.flush()


async def test_file_bin_truncate(file_bin, tmp_path):
    await file_bin.truncate()
    with (tmp_path / "bin").open("rb") as file:
        assert file.read() == b""


@pytest.fixture(name="file_append")
def fixture_file_append(client, device, seed_tmp):
    return RpcFile(client, "test/device/files/bin", RpcFile.Flag.APPEND)


async def test_file_bin_append(file_append, tmp_path):
    file_append.offset = 0
    await file_append.write(b"def")
    file_append.offset = 0
    with (tmp_path / "bin").open("rb") as file:
        assert file.read() == b"abcdef"


@pytest.fixture(name="file_buffered")
def fixture_file_buffered(client, device, seed_tmp):
    return RpcFile(client, "test/device/files/bin", RpcFile.Flag.BUFFERED)


async def test_file_buffered_read(file_buffered, tmp_path):
    assert file_buffered.offset == 0
    assert await file_buffered.read(1) == b"a"
    assert file_buffered.offset == 1
    assert await file_buffered.read(1) == b"b"
    assert file_buffered.offset == 2
    assert await file_buffered.read(2) == b"c"
    assert file_buffered.offset == 3
    assert await file_buffered.read(2) == b""
    assert file_buffered.offset == 3
    with (tmp_path / "bin").open("ab") as file:
        file.write(b"def")
    assert await file_buffered.read(2) == b"de"
    assert file_buffered.offset == 5


async def test_file_buffered_write(file_buffered, tmp_path):
    file_buffered.offset = await file_buffered.size()
    await file_buffered.write(b"de")
    await file_buffered.write(b"f")
    with (tmp_path / "bin").open("rb") as file:
        assert file.read() == b"abc"
    await file_buffered.flush()
    with (tmp_path / "bin").open("rb") as file:
        assert file.read() == b"abcdef"

    await file_buffered.write(b"gh")
    file_buffered.offset = 1
    await file_buffered.write(b"d")
    with (tmp_path / "bin").open("rb") as file:
        assert file.read() == b"abcdefgh"
