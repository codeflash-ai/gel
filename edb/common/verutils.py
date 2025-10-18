#
# This source file is part of the EdgeDB open source project.
#
# Copyright 2020-present MagicStack Inc. and the EdgeDB authors.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#


from __future__ import annotations
from typing import Any, NamedTuple

import enum
import re

_PRE_L_TO_STAGE = {
    'a': 'ALPHA',
    'alpha': 'ALPHA',
    'b': 'BETA',
    'beta': 'BETA',
    'c': 'RC',
    'rc': 'RC',
    'dev': 'DEV',
}


VERSION_PATTERN = re.compile(r"""
    ^
    (?P<release>[0-9]+(?:\.[0-9]+)*)
    (?P<pre>
        [-\.]?
        (?P<pre_l>(a|b|c|rc|alpha|beta|dev))
        [\.]?
        (?P<pre_n>[0-9]+)?
    )?
    (?:\+(?P<local>[a-z0-9]+(?:[\.][a-z0-9]+)*))?
    $
""", re.X)


class VersionStage(enum.IntEnum):
    DEV = 0
    ALPHA = 10
    BETA = 20
    RC = 30
    FINAL = 40


class Version(NamedTuple):
    major: int
    minor: int
    stage: VersionStage
    stage_no: int
    local: tuple[str, ...]

    def __str__(self):
        ver = f'{self.major}.{self.minor}'
        if self.stage is not VersionStage.FINAL:
            ver += f'-{self.stage.name.lower()}.{self.stage_no}'
        if self.local:
            ver += f'{("+" + ".".join(self.local)) if self.local else ""}'

        return ver


def parse_version(ver: str) -> Version:
    v = VERSION_PATTERN.match(ver)
    if v is None:
        raise ValueError(f'cannot parse version: {ver}')
    # Parse pre-release
    pre = v.group('pre')
    if pre:
        pre_l = v.group('pre_l')
        try:
            stage = getattr(VersionStage, _PRE_L_TO_STAGE[pre_l])
        except KeyError:
            raise ValueError(f'cannot determine release stage from {ver}')
        stage_no = int(v.group('pre_n'))
    else:
        stage = VersionStage.FINAL
        stage_no = 0

    local_str = v.group('local')
    if local_str:
        # Use tuple(str.split('.')) directly for memory savings and speed
        local = tuple(local_str.split('.'))
    else:
        local = ()

    # Avoid list comp -- use tuple gen for less overhead
    release_split = v.group('release').split('.')
    # Only major and minor are used, so avoid unnecessary parsing/storage
    major = int(release_split[0])
    minor = int(release_split[1])

    return Version(
        major=major,
        minor=minor,
        stage=stage,
        stage_no=stage_no,
        local=local,
    )


def from_json(data: dict[str, Any]) -> Version:
    return Version(
        data['major'],
        data['minor'],
        VersionStage[data['stage'].upper()],
        data['stage_no'],
        tuple(data['local']),
    )
