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
from .podcast_episode import PodcastEpisode

class PodcastChannel(MediaBase):
    def __init__(self, info):
        self._url = get_key(info, 'url')
        self._title = get_key(info, 'title')
        self._description = get_key(info, 'description')
        self._status = get_key(info, 'status')
        self._original_image_url = get_key(info, 'originalImageUrl')
        self._episodes = []
        if 'episode' in info and info['episode']:
            for entry in info['episode']:
                self._episodes.append(PodcastEpisode(entry))
        super().__init__(info)

    def to_dict(self):
        ret = super().to_dict()
        ret['url'] = self._url
        ret['title'] = self._title
        ret['description'] = self._description
        ret['status'] = self._status
        ret['originalImageUrl'] = self._original_image_url
        if self._episodes:
            ret['episode'] = [entry.to_dict() for entry in self._episodes]
        return ret

    url = property(lambda s: s._url)
    title = property(lambda s: s._title)
    description = property(lambda s: s._description)
    status = property(lambda s: s._status)
    original_image_url = property(lambda s: s._original_image_url)
    episodes = property(lambda s: s._episodes)
