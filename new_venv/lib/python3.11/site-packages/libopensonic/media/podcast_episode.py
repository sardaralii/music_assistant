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

from .media_base import MediaBase, get_key

class PodcastEpisode(MediaBase):
    def __init__(self, info):
        self._stream_id = get_key(info, 'streamId')
        self._channel_id = get_key(info, 'channelId')
        self._title = get_key(info, 'title')
        self._description = get_key(info, 'description')
        self._publish_date = get_key(info, 'publishDate')
        self._status = get_key(info, 'status')
        self._parent = get_key(info, 'parent')
        self._is_dir = get_key(info, 'isDir')
        self._year = get_key(info, 'year')
        self._genre = get_key(info, 'genre')
        self._size = get_key(info, 'size')
        self._duration = get_key(info, 'duration')
        self._bitrate = get_key(info, 'bitrate')
        self._path = get_key(info, 'path')
        self._suffix = get_key(info, 'suffix')
        self._content_type = get_key(info, 'contentType')
        super().__init__(info)

    def to_dict(self):
        ret = super().to_dict()
        ret['streamId'] = self._stream_id
        ret['channelId'] = self._channel_id
        ret['title'] = self._title
        ret['description'] = self._description
        ret['publishDate'] = self._publish_date
        ret['status'] = self._status
        ret['parent'] = self._parent
        ret['isDir'] = self._is_dir
        ret['year'] = self._year
        ret['genre'] = self._genre
        ret['size'] = self._size
        ret['duration'] = self._duration
        ret['bitrate'] = self._bitrate
        ret['path'] = self._path
        ret['suffix'] = self._suffix
        ret['contentType'] = self._content_type
        return ret

    stream_id = property(lambda s: s._stream_id)
    channel_id = property(lambda s: s._channel_id)
    title = property(lambda s: s._title)
    description = property(lambda s: s._description)
    publish_date = property(lambda s: s._publish_date)
    status = property(lambda s: s._status)
    parent = property(lambda s: s._parent)
    is_dir = property(lambda s: s._is_dir)
    year = property(lambda s: s._year)
    genre = property(lambda s: s._genre)
    size = property(lambda s: s._size)
    duration = property(lambda s: s._duration)
    bitrate = property(lambda s: s._bitrate)
    path = property(lambda s: s._path)
    suffix = property(lambda s: s._suffix)
    content_type = property(lambda s: s._content_type)
