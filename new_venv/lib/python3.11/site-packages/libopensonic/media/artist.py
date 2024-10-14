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
from .album import Album

class ArtistInfo:
    """
    Holds extra (optional) artist info
    """
    def __init__(self, info):
        self._biography = get_key(info, 'biography', '')
        self._mb_id = get_key(info, 'musicBrainzId', '')
        self._small_url = get_key(info, 'smallImageUrl', '')
        self._med_url = get_key(info, 'mediumImageUrl', '')
        self._large_url = get_key(info, 'largeImageUrl', '')
        self._lastfm_url = get_key(info, 'lastFmUrl', '')
        self._similar_artists = []
        if 'similarArtists' in info:
            for entry in info['similarArtists']:
                self._similar_artists.append(Artist(entry))

    def to_dict(self):
        ret = {
            'biography': self._biography,
            'musicBrainzId': self._mb_id,
            'smallImageUrl': self._small_url,
            'mediumImageUrl': self._med_url,
            'largeImageUrl': self._large_url,
            'lastFmUrl': self._lastfm_url
        }
        if self._similar_artists:
            ret['similarArtists'] = [entry.to_dict() for entry in self._similar_artists]
        return ret
    
    biography = property(lambda s: s._biography)
    mb_id = property(lambda s: s._mb_id)
    small_url = property(lambda s: s._small_url)
    med_url = property(lambda s: s._med_url)
    large_url = property(lambda s:s._large_url)
    lastfm_url = property(lambda s:s._lastfm_url)
    similar_artists = property(lambda s:s._similar_artists)


class Artist(MediaBase):
    """
    A subsonic Artist
    """
    def __init__(self, info):
        """
        Builds an Artist object

        info:dict                   A dict from the JSON response to getArtist
                                    Must contain fields for MediaBase and 'name',
                                    'albumCount', and 'album' though 'album'
                                    is a list and can be an empty one
        """
        self._album_count = get_key(info, 'albumCount')
        self._name = self.get_required_key(info, 'name', '')
        self._sort_name = self.get_required_key(info, 'sortName', '')
        self._info = None
        self._artist_image_url = get_key(info, 'artistImageUrl')
        self._sort_name = get_key(info, 'sortName')
        self._roles = get_key(info, 'roles')
        self._albums = []
        if 'album' in info and info['album']:
            for entry in info['album']:
                self._albums.append(Album(entry))
        super().__init__(info)

    def to_dict(self):
        ret = super().to_dict()
        ret['albumCount'] = self._album_count
        ret['sortName'] = self._sort_name
        ret['name'] = self._name
        ret['artistImageUrl'] = self._artist_image_url
        if self._info is not None:
            ret['info'] = self._info.to_dict()
        ret['sortName'] = self._sort_name
        ret['roles'] = self._roles
        if self._albums:
            ret['album'] = [entry.to_dict() for entry in self._albums]
        return ret

    album_count = property(lambda s: s._album_count)
    artist_image_url = property(lambda s: s._artist_image_url)
    name = property(lambda s: s._name)
    sort_name = property(lambda s: s._sort_name)
    albums = property(lambda s: s._albums)
    def set_info(self, info: ArtistInfo):
        self._info = info
    info = property(lambda s: s._info, set_info)
    sort_name = property(lambda s: s._sort_name)
    roles = property(lambda s: s._roles)
    mb_id = property(lambda s: s._info.mb_id if s._info is not None else '')
