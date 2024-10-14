"""
This file is part of py-opensonic.

py-opensonic is free software: you can redistribute it and/or modify
it under the terms of the GNU General Public License as published by
the Free Software Foundation, either version 3 of the License, or
(at your option) any later version.

py-opensonic is distributed in the hope that it will be useful,
but WITHOUT ANY WARRANTY; without even the implied warranty of
MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
GNU General Public License for more details.

You should have received a copy of the GNU General Public License
along with py-opensonic.  If not, see <http://www.gnu.org/licenses/>
"""

from warnings import warn


def get_key(store, key, default=None):
    """
    Quality of life helper function to give the keyed value if it exists,
    the default specified (None if not specified) otherwise.
    """
    return store[key] if key in store else default


class Cover:
    def __init__(self, my_type, my_bytes):
        self._type = my_type
        self._bytes = my_bytes
    type = property(lambda s: s._type)
    bytes = property(lambda s: s._bytes)


class MediaBase:
    """
    Base class for media items, this class should not be used directly
    """
    def __init__(self, info):
        """
        The Media class consolidates fields and methods common to all "Media" things
        (e.g. Songs, Albums, Artists, Podcasts, etc)

        info:dict                           A dict from the JSON response to any get request
                                            Must contain id field
                                            May contain coverArt and starred field
        """
        self._id = self.get_required_key(info, 'id')
        self._cover_id = get_key(info, 'coverArt')
        self._starred = get_key(info, 'starred')

    def to_dict(self):
        """
        Return a dictonary representation of self.
        """
        return {'id': self._id, 'coverId': self._cover_id, 'starred': self._starred}

    @classmethod
    def get_class_name(cls):
        return cls.__name__

    id = property(lambda s: s._id)
    cover_id = property(lambda s: s._cover_id)
    starred = property(lambda s: s._starred)

    def get_required_key(self, store, key, default=None):
        """
        Used when parsing server returns for keys that are marked required by the specification.
        """
        if key in store:
            return store[key]
        warn(f"{self.get_class_name()} object returned by server is missing required field '{key}'")
        return default
