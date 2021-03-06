# -*- coding: utf-8 -*-
#
# Copyright (C) 2019 Chris Caron <lead2gold@gmail.com>
# All rights reserved.
#
# This code is licensed under the MIT License.
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files(the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and / or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions :
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
import os
import tempfile
import shutil
import gzip
import apprise
import hashlib
import errno

from django.conf import settings


class AppriseConfigCache(object):
    """
    Designed to make it easy to store/read contact back from disk in a cache
    type structure that is fast.
    """

    def __init__(self, cache_root, salt="apprise"):
        """
        Works relative to the cache_root
        """
        self.root = cache_root
        self.salt = salt.encode()

    def put(self, key, content, fmt):
        """
        Based on the key specified, content is written to disk (compressed)

        key:     is an alphanumeric string needed to write and read back this
                 file being written.
        content: the content to be written to disk
        fmt:     the content config format (of type apprise.ConfigFormat)

        """
        # There isn't a lot of error handling done here as it is presumed most
        # of the checking has been done higher up.

        # First two characters are reserved for cache level directory writing.
        path, filename = self.path(key)
        os.makedirs(path, exist_ok=True)

        # Write our file to a temporary file
        _, tmp_path = tempfile.mkstemp(suffix='.tmp', dir=path)
        try:
            with gzip.open(tmp_path, 'wb') as f:
                # Write our content to disk
                f.write(content.encode())

        except OSError:
            # Handle failure
            os.remove(tmp_path)
            return False

        # If we reach here we successfully wrote the content. We now safely
        # move our configuration into place. The following writes our content
        # to disk as /xx/key.fmt
        shutil.move(tmp_path, os.path.join(
            path, '{}.{}'.format(filename, fmt)))

        # perform tidy of any other lingering files of other type in case
        # configuration changed from TEXT -> YAML or YAML -> TEXT
        if self.clear(key, set(apprise.CONFIG_FORMATS) - {fmt}) is False:
            # We couldn't remove an existing entry; clear what we just created
            self.clear(key, {fmt})
            # fail
            return False

        return True

    def get(self, key):
        """
        Based on the key specified, content is written to disk (compressed)

        key:     is an alphanumeric string needed to write and read back this
                 file being written.

        The function returns a tuple of (content, fmt) where the content
        is the uncompressed content found in the file and fmt is the
        content representation (of type apprise.ConfigFormat).

        If no data was found, then (None, None) is returned.
        """

        # There isn't a lot of error handling done here as it is presumed most
        # of the checking has been done higher up.

        # First two characters are reserved for cache level directory writing.
        path, filename = self.path(key)

        # prepare our format to return
        fmt = None

        # Test the only possible hashed files we expect to find
        text_file = os.path.join(
            path, '{}.{}'.format(filename, apprise.ConfigFormat.TEXT))
        yaml_file = os.path.join(
            path, '{}.{}'.format(filename, apprise.ConfigFormat.YAML))

        if os.path.isfile(text_file):
            fmt = apprise.ConfigFormat.TEXT
            path = text_file

        elif os.path.isfile(yaml_file):
            fmt = apprise.ConfigFormat.YAML
            path = yaml_file

        else:
            # Not found; we set the fmt to something other than none as
            # an indication for the upstream handling to know that we didn't
            # fail on error
            return (None, '')

        # Initialize our content
        content = None
        try:
            with gzip.open(path, 'rb') as f:
                # Write our content to disk
                content = f.read().decode()

        except OSError:
            # all none return means to let upstream know we had a hard failure
            return (None, None)

        # return our read content
        return (content, fmt)

    def clear(self, key, formats=None):
        """
        Removes any content associated with the specified key should it
        exist.

        None is returned if there was nothing to clear
        True is returned if content was cleared
        False is returned if an internal error prevented data from being
              cleared
        """
        # Default our response None
        response = None

        if formats is None:
            formats = apprise.CONFIG_FORMATS

        path, filename = self.path(key)
        for fmt in formats:
            # Eliminate any existing content if present
            try:
                # Handle failure
                os.remove(os.path.join(path, '{}.{}'.format(filename, fmt)))

                # If we reach here, an element was removed
                response = True

            except OSError as e:
                if e.errno != errno.ENOENT:
                    # We were unable to remove the file
                    response = False

        return response

    def path(self, key):
        """
        returns the path and filename content should be written to based on the
        specified key
        """
        encoded_key = hashlib.sha224(self.salt + key.encode()).hexdigest()
        path = os.path.join(self.root, encoded_key[0:2])
        return (path, encoded_key[2:])


# Initialize our singleton
ConfigCache = AppriseConfigCache(
    settings.APPRISE_CONFIG_DIR, salt=settings.SECRET_KEY)
