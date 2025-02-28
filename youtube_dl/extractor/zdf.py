import operator
import re

from .common import InfoExtractor
from ..utils import (
    parse_xml_doc,
    unified_strdate,
)


class ZDFIE(InfoExtractor):
    _VALID_URL = r'^http://www\.zdf\.de\/ZDFmediathek(?P<hash>#)?\/(.*beitrag\/video\/)(?P<video_id>[^/\?]+)(?:\?.*)?'

    def _real_extract(self, url):
        mobj = re.match(self._VALID_URL, url)
        video_id = mobj.group('video_id')

        xml_url = u'http://www.zdf.de/ZDFmediathek/xmlservice/web/beitragsDetails?ak=web&id=%s' % video_id
        info_xml = self._download_webpage(
            xml_url, video_id, note=u'Downloading video info')
        doc = parse_xml_doc(info_xml)

        title = doc.find('.//information/title').text
        description = doc.find('.//information/detail').text
        uploader_node = doc.find('.//details/originChannelTitle')
        uploader = None if uploader_node is None else uploader_node.text
        duration_str = doc.find('.//details/length').text
        duration_m = re.match(r'''(?x)^
            (?P<hours>[0-9]{2})
            :(?P<minutes>[0-9]{2})
            :(?P<seconds>[0-9]{2})
            (?:\.(?P<ms>[0-9]+)?)
            ''', duration_str)
        duration = (
            (
                (int(duration_m.group('hours')) * 60 * 60) +
                (int(duration_m.group('minutes')) * 60) +
                int(duration_m.group('seconds'))
            )
            if duration_m
            else None
        )
        upload_date = unified_strdate(doc.find('.//details/airtime').text)

        def xml_to_format(fnode):
            video_url = fnode.find('url').text
            is_available = u'http://www.metafilegenerator' not in video_url

            format_id = fnode.attrib['basetype']
            format_m = re.match(r'''(?x)
                (?P<vcodec>[^_]+)_(?P<acodec>[^_]+)_(?P<container>[^_]+)_
                (?P<proto>[^_]+)_(?P<index>[^_]+)_(?P<indexproto>[^_]+)
            ''', format_id)

            ext = format_m.group('container')
            is_supported = ext != 'f4f'

            PROTO_ORDER = ['http', 'rtmp', 'rtsp']
            try:
                proto_pref = -PROTO_ORDER.index(format_m.group('proto'))
            except ValueError:
                proto_pref = 999

            quality = fnode.find('./quality').text
            QUALITY_ORDER = ['veryhigh', '300', 'high', 'med', 'low']
            try:
                quality_pref = -QUALITY_ORDER.index(quality)
            except ValueError:
                quality_pref = 999

            abr = int(fnode.find('./audioBitrate').text) // 1000
            vbr = int(fnode.find('./videoBitrate').text) // 1000
            pref = (is_available, is_supported,
                    proto_pref, quality_pref, vbr, abr)

            format_note = u''
            if not is_supported:
                format_note += u'(unsupported)'
            if not format_note:
                format_note = None

            return {
                'format_id': format_id + u'-' + quality,
                'url': video_url,
                'ext': ext,
                'acodec': format_m.group('acodec'),
                'vcodec': format_m.group('vcodec'),
                'abr': abr,
                'vbr': vbr,
                'width': int(fnode.find('./width').text),
                'height': int(fnode.find('./height').text),
                'filesize': int(fnode.find('./filesize').text),
                'format_note': format_note,
                '_pref': pref,
                '_available': is_available,
            }

        format_nodes = doc.findall('.//formitaeten/formitaet')
        formats = sorted(filter(lambda f: f['_available'],
                                map(xml_to_format, format_nodes)),
                         key=operator.itemgetter('_pref'))

        return {
            'id': video_id,
            'title': title,
            'formats': formats,
            'description': description,
            'uploader': uploader,
            'duration': duration,
            'upload_date': upload_date,
        }
