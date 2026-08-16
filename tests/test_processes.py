import subprocess
import unittest
from unittest import mock

try:
    from pipeline.processes import detached_popen_kwargs, launch_detached
except ImportError:
    detached_popen_kwargs = None
    launch_detached = None


class TestDetachedProcesses(unittest.TestCase):
    def test_windows_detached_kwargs_redirect_stdio_and_set_flags(self):
        self.assertIsNotNone(detached_popen_kwargs)
        if detached_popen_kwargs is None:
            return
        kwargs = detached_popen_kwargs(platform="windows")
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)
        self.assertIs(kwargs["stdout"], subprocess.DEVNULL)
        self.assertIs(kwargs["stderr"], subprocess.DEVNULL)
        self.assertTrue(kwargs["creationflags"])
        self.assertTrue(kwargs["close_fds"])

    def test_posix_detached_kwargs_start_new_session(self):
        self.assertIsNotNone(detached_popen_kwargs)
        if detached_popen_kwargs is None:
            return
        kwargs = detached_popen_kwargs(platform="posix")
        self.assertTrue(kwargs["start_new_session"])
        self.assertIs(kwargs["stdin"], subprocess.DEVNULL)

    def test_launch_detached_does_not_wait_for_child(self):
        self.assertIsNotNone(launch_detached)
        if launch_detached is None:
            return
        fake = mock.Mock(pid=1234)
        with mock.patch("pipeline.processes.subprocess.Popen", return_value=fake) as popen:
            result = launch_detached(["viewer.exe", "asset.ply"], cwd=".", platform="posix")
        self.assertIs(result, fake)
        self.assertEqual(result.pid, 1234)
        popen.assert_called_once()


if __name__ == "__main__":
    unittest.main()
