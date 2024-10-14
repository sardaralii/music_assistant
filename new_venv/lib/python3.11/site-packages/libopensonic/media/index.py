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

from .artist import Artist

class Index:
    """
    All of the endpoints which return multiple Artists return them grouped
    by the first letter in their name. This object is one entry in the list
    of grouped artists.
    
    name:str            The first letter of all the artists names in this 
                        group.
    artists:list        This is a list of media.Artist
    """
    def __init__(self, info):
        self._name = info['name']
        self._artists = []
        for entry in info['artist']:
            self._artists.append(Artist(entry))

    name = property(lambda s: s._name)
    artists = property(lambda s: s._artists)