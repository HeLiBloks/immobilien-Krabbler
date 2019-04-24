#!/usr/bin/env python3
# -*- coding: utf-8 -*-

# immoKrabbler.py crawl objects from immobilienscout24 and save them to a RDMS
# Copyright © 2019 Henrik Lindgren (henrikprojekt at googlemail dot com)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


from sqlalchemy import create_engine
from sqlalchemy import MetaData
from sqlalchemy import Table
from sqlalchemy import Column
from sqlalchemy import Integer, String, Boolean, Numeric, ForeignKey, select, DateTime
from sqlalchemy_utils import JSONType  # , CurrencyType, Currency as EUR
import re
import datetime
import json
import demjson
import sys
import os

def uniqDicts(listOfDicts, debug=False):
    """returns unique list of dicts"""
    if debug:
        items = len(listOfDicts)
        listOfDicts = list({dic['id']: dic for dic in listOfDicts}.values())
        print('{0} non uniqe items removed from list of dicts'.format(items-len(listOfDicts)))
        return listOfDicts
    else:
        return list({dic['id']: dic for dic in listOfDicts}.values())

def validate_url(url):
    """validates a baseurl, this is the url of the search result on the immobilienscout page
    :url: alike 'https://www.immobilienscout24.de/Suche/S-T/Wohnung-Miete/Umkreissuche/Gotha/99867/48730/2334359/
    -/-/5?enteredFrom=one_step_search'
    :returns: True or False
    """
    pattern = re.compile(r'(https?[:]\/\/)?www\.immobilienscout24\.\w+\/Suche')
    try:
        assert pattern.match(url)
    except Exception as e:
        raise """url is of wrong format %r it should be something like:\n
        https://www.immobilienscout24.de/Suche/S-T/Wohnung-Miete/Umkreissuche/Gotha/99867/48730/2334359/
        -/-/5?enteredFrom=one_step_search""" % url

class database(object):
    """class immobilien db"""

    def __init__(self, db_uri='sqlite:///immobilien.db', debug=False):
        """constructor """
        self.debug = debug
        self.db_uri = db_uri
        self.engine = create_engine(db_uri, echo=self.debug)
        self.metadata = MetaData(self.engine)
        #  self.encoding =
        self.immobilien = Table('immobilien', self.metadata,
                                Column('id', Integer(), primary_key=True),
                                Column('search_url', String(2000)),
                                Column('unixtimestamp', Integer(),
                                       default=datetime.datetime.now(datetime.timezone.utc).timestamp()),
                                Column('cwid', String()),
                                Column('shortlisted', String()),
                                Column('privateoffer', String()),
                                Column('title', String(255)),
                                Column('address', String(255)),
                                Column('district', String(255)),
                                Column('city', String(255)),
                                Column('zip', Integer()),
                                Column('distanceinkm', Integer()),
                                Column('hasnewflag', String()),
                                Column('hasfloorplan', String()),
                                Column('hasvaluation', String()),
                                Column('realtorlogoforresultlisturl', String()),
                                Column(u'realtorcompanyname', String()),
                                Column('contactname', String()),
                                Column('kaltmiete', Numeric()),
                                Column('kaufpreis', Numeric()),
                                Column('wohnfläche', Numeric()),
                                Column('grundstück', Integer()),
                                Column('zimmer', Integer()),
                                Column('idtohide', Integer()),
                                Column('listingsize', String(3)),
                                Column('latitude', Numeric()),
                                Column('longitude', Numeric()),
                                Column('checkedattributes', JSONType()),
                                Column('gallerypictures', JSONType()))

        self.checkedAttributes = Table('checkedAttributes', self.metadata,
                                       Column('id', Integer(), primary_key=True),
                                       Column('attribute', String(), unique=True))

        self.immobilienAttributes = Table('immobilienAttributes', self.metadata,
                                          Column('id', Integer(), primary_key=True),
                                          Column('immobilie_fk', Integer(), ForeignKey('immobilien.id')),
                                          Column('checkedAttributes_fk', Integer(), ForeignKey('immobilien.id'), unique=True))

        self.url = Table('url', self.metadata,
                         Column('id', Integer(), primary_key=True),
                         Column('url', Integer()))

        self.metadata.create_all()
        self.conn = self.engine.connect()

    def insertimmobilie(self, immobilienList):
        """
        :immobilienList: list of dicts containing immobilien to insert
        :returns: list of inserted ids
        """
        assert isinstance(immobilienList, list), "immobilienList is not a list: %r" % immobilienList
        # grab all scraped id's
        ids = set(int(immo['id']) for immo in immobilienList)
        #  print(ids, [print(imm['id']) for imm in immobilienList])
        if self.debug:
            assert len(ids) == len(immobilienList), 'arg immobilienList contains duplicate entries {0} uniq vs {1} in given'.format(
                len(ids), len(immobilienList))
            print('atempting to insert id''s', ids)
        # for select() syntax see http://docs.sqlalchemy.org/en/latest/core/selectable.html
        db_immobilieIDs = self.conn.execute(
            select([self.immobilien.c.id]).where(
                self.immobilien.c.id.in_(ids)))
        db_immobilieIDs = [int(iid[0]) for iid in db_immobilieIDs]
        if self.debug:
            if len(db_immobilieIDs) is not 0:
                print('id''s already in db', db_immobilieIDs)
        insertList = [ immo for immo in immobilienList if int(immo['id']) not in db_immobilieIDs ]
        #  for immo in immobilienList:
        #  if int(immo['id']) not in db_immobilieIDs:
        #  insertList.append(immo)

        if len(insertList) is not 0:
            if self.debug:
                print('inserting immos with id: ', [immo['id'] for immo in insertList])
            return self.conn.execute(self.immobilien.insert(), insertList)
        else:
            if self.debug:
                print('no objects to insert ')
            return ()

    def selectUniqeSearchUrls(self, pattern='.+[A-Z]-[A-Z]\/(?![A-Z][-][0-9]).+'):
        """returns unique urls matching re pattern from the db"""
        # TODO:remove python regex in favor of:
        # 'SELECT DISTINCT search_url FROM immobilien WHERE search_url NOT LIKE "%s-t/p%'
        urls = self.conn.execute(
            select([self.immobilien.c.search_url]).distinct().where(
                self.immobilien.c.search_url.like('%S-T%')))
        # convert db proxyobject to list of strings
        urls = [u[0] for u in urls]
        pattern = re.compile(pattern)
        urls = list(filter(lambda url: pattern.match(url), urls))
        if self.debug is True:
            print('uniqe urls:{0}, matching pattern:{1}'.format(len(urls), pattern))
        return urls

    def insertcheckedAttributes(self, immobilien):
        """
        list of dicts immobilien
        :returns: list of inserted ids
        """
        insertedAttributes = []
        # TODO: make this more functional
        attributes = set([attr for d in immobilien for attr in d['checkedattributes']])
        id_attributes = select([self.checkedAttributes.c.id, self.checkedAttributes.c.attribute]).where(
            self.checkedAttributes.c.attribute.in_(attributes))
        for immobilie in immobilien:
            attribute = immobilie['checkedattributes']
            #  print(attribute)
            for attr in attribute:
                AttributeinDB = self.conn.execute(
                    select([self.checkedAttributes.c.id]).where(
                        self.checkedAttributes.c.attribute == attr)).scalar()
                if AttributeinDB is None:
                    attr = self.conn.execute(
                        self.checkedAttributes.insert(), {'attribute': attr})  # .inserted_primary_key[0]
                    if self.debug:
                        print(
                            'INFO:inserted checkedAttribute into db, assigned id:', AttributeinDB)
                else:
                    attr = AttributeinDB
                    if self.debug:
                        print('INFO:checkedAttribute already in db :', AttributeinDB, attr)
                insertedAttributes.append(AttributeinDB)
        return insertedAttributes

    def insertimmobilienAttributes(self, listOfcheckedAttributes_key, immobilien):
        """insertimmobilienAttributes.
        :immobilie_key: from immobilie table
        :listOfcheckedAttributes_key: list of checkedAttributes_key
        :returns: inserted or selected ids
        TODO: fix this method
        """
        "is not a dictionary: %r" % immobilienList
        immobilienAttributes = []
        for immobilie in immobilien:
            for listOfcheckedAttributes_key in immobilie['checkedattributes']:
                #  print(checkedAttributes_key)
                keyCombination = self.conn.execute(
                    select([self.immobilienAttributes.c.id]).where(
                        self.immobilienAttributes.c.immobilie_fk == immobilie_key).where(
                            self.checkedAttributes.c.checkedAttributes_fk == checkedAttributes_key).scalar())
                if keyCombination is None:
                    keyCombination = self.conn.execute(
                        self.immobilienAttributes.insert(),
                        {'checkedAttributes_fk': checkedAttributes_key,
                         'immobilie_fk': immobilie_key}).inserted_primary_key[0]
                    if self.debug:
                        print('inserted immobilienAttributes into db assigned id:', keyCombination)
                else:
                    if self.debug:
                        print('immobilienAttributes already in db ', keyCombination)
                immobilienAttributes.append(keyCombination)
        return immobilienAttributes

class Immo_scraper(object):
    """
    scrapes immobilienscout24 resultlist urls for 'property' (immobilien)
    """

    def __init__(self, urls=[], imagepath='immoPhotos', debug=False):
        """initializes Immo_scraper class

        :url: List of urls to scrape
        """
        assert isinstance(urls, list), "urls is not a list"
        from selenium import webdriver
        #  import locale
        self.imagepath = imagepath
        self.immobilien = []
        self.debug = debug
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (iPhone; U; CPU like Mac OS X; en) AppleWebKit/420.1'
            ' (KHTML, like Gecko) Version/3.0 Mobile/3B48b Safari/419.3'}
        for key, value in enumerate(self.headers):
            webdriver.DesiredCapabilities.PHANTOMJS[
                'phantomjs.page.customHeaders.{}'.format(key)] = value
        # use phantomJS to render the JS
        self._seleniumdriver = webdriver.PhantomJS(
            service_args=['--disk-cache=true', '--disk-cache-path=phantomjs_cache',
                          '--load-images=false', '--ignore-ssl-errors=true', '--ssl-protocol=any'])
        # urls from immosearch
        self.baseurls = urls
        if len(urls) > 0:
            #  print(urls)
            for url in self.baseurls:
                base_jsn = self._scrape_baseurl(url)
                #  convert scraped JS to json
                base_jsn = self._jsn2immobilie(base_jsn)
                self.immobilien.extend(base_jsn)
            self.immobilien = uniqDicts(self.immobilien)
            #  self._seleniumdriver.close()

    def _jsn2immobilie(self, listofjsn=[], debug=False):
        """
        extracts immobilien, adds missing values from list of dicts
        :listofjson: list of dicts
        returns list of dicts
        """
        assert isinstance(listofjsn, list), 'is not a list %r' % listofjsn
        if len(listofjsn) is 0:
            return []
        #  assert isinstance(listofjsn[0], dict), 'is not a list of dicts %r' % listofjsn
        immobilien = []
        defaultvalues = {'Kaltmiete': None,
                         'latitude': None,
                         'longitude': None,
                         'idToHide': None,
                         'Grundstück': None,
                         'distanceInKm': None,
                         'realtorCompanyName': None,
                         'Kaufpreis': None,
                         'realtorLogoForResultlistUrl': None,
                         'checkedAttributes': None,
                         'contactname': None,
                       'galleryPictures': [],
                         'Wohnfläche': None}
        # remove @ from key names @id...
        keyname = re.compile(r'@(?=[\w\.]+[''"]\s?:)')
        immo_str = json.dumps(listofjsn)
        #  immo_str = demjson.decode(listofjsn)
        immo_str = re.sub(keyname, '', immo_str)

        #  keyname = re.compile(r'(["\'])[fF]alse\1')
        #  immo_str = re.sub(keyname, False, immo_str)
        listofjsn = json.loads(immo_str)
        subpattern = re.compile(r'[^\d,]')

        def _clean_cash(attrib):
            """clean out ambiguous chars
            :dictionary: to clean
            :returns: cleaned dictionary
            """
            attrib = attrib.replace('€', '',)
            attrib = attrib.replace('.', '')
            attrib = attrib.replace(',', '.')
            return attrib

        for immobilie in listofjsn:
            # merge attribute list of dicts [ { title:Kaufpreis,
            # value:'1000 €'},...] with parent
            #  if self.debug is True:
                #  print('extracted immobilie from json:', immobilie['attributes'])
            # TODO: move attributes to its own table for purpose of
            # normalisation
            #  unpack attributes
            if 'attributes' in immobilie:
                for attrib in immobilie['attributes']:
                    for attr in attrib['attribute']:
                        immobilie[attr['label']] = attr['value']
                immobilie.pop('attributes', None)

            if 'Grundstück' in immobilie:
                immobilie['Grundstück'] = immobilie['Grundstück'].replace(' m²', '')
                immobilie['Grundstück'] = immobilie['Grundstück'].replace(',', '.')
            if 'Wohnfläche' in immobilie:
                immobilie['Wohnfläche'] = immobilie['Wohnfläche'].replace(' m²', '')
                immobilie['Wohnfläche'] = immobilie['Wohnfläche'].replace(',', '.')
            if 'Kaufpreis' in immobilie:
                immobilie['Kaufpreis'] = _clean_cash(immobilie['Kaufpreis'])
            if 'Kaltmiete' in immobilie:
                immobilie['Kaltmiete'] = _clean_cash(immobilie['Kaltmiete'])

            # unpack json
            if 'resultlist.realEstate' in immobilie:
                if 'title' in immobilie['resultlist.realEstate']:
                    immobilie['title'] = immobilie['resultlist.realEstate']['title']
            if 'address' in immobilie:
                immobilie['address'] = immobilie['resultlist.realEstate']['address']['description']['text']
            if 'calculatedprice' in immobilie:
                immobilie['calculatedprice'] = immobilie['resultlist.realEstate']['calculatedPrice']['value']

            immobilie['checkedattributes'] = []
            if 'realEstateTags' in immobilie:
                if isinstance(immobilie['realEstateTags'], list):
                    immobilie['checkedattributes'] = immobilie['realEstateTags'].values()

            if 'resultlist.realEstate' in immobilie:
                if 'garden' in immobilie['resultlist.realEstate']:
                    immobilie['checkedattributes'].append('garden')
                if 'balcony' in immobilie['resultlist.realEstate']:
                    immobilie['checkedattributes'].append('balcony')
                if 'builtInKitchen' in immobilie['resultlist.realEstate']:
                    immobilie['checkedattributes'].append('builtInKitchen')
                try:
                    if 'contactDetails' in immobilie['resultlist.realEstate'] and immobilie['resultlist.realEstate']['contactDetails'] is not None:
                        immobilie['contactname'] = immobilie['resultlist.realEstate']['contactDetails'][
                            'firstname']+' '+immobilie['resultlist.realEstate']['contactDetails']['lastname']
                except Exception as e:
                    if self.debug:
                        print('key not found in dict', e, immobilie['resultlist.realEstate']['contactDetails'])
                else:
                    immobilie['contactname'] = immobilie['resultlist.realEstate']['contactDetails']['lastname']

                if immobilie['resultlist.realEstate']['listingType']:
                    immobilie['listingsize'] = immobilie['resultlist.realEstate']['listingType']
                try:
                    if immobilie['resultlist.realEstate']['galleryAttachments'] is not None:
                        immobilie['gallerypictures'] = [x['xlink.href']
                                                        for x in immobilie['resultlist.realEstate']['galleryAttachments']['attachment']]
                except Exception as e:
                    print([x for x in immobilie['resultlist.realEstate']])

            # merge dicts to append missing values
            immobilie = {**defaultvalues, **immobilie}
            # lowercase
            immobilie = dict((k.lower(), v) for k, v in immobilie.items())
            immobilien.append(immobilie)
        #  [ print('cleaned immobilien with id''s',ids['id']) for ids in immobilie ]
        return immobilien

    class Immobilie(object):
        """Docstring for Immobilie. """

        def __init__(self, json=[]):
            """creates an immbobilien instance from a dict or iterable
            :json: TODO
            """
            if isinstance(json, dict):
                self.id = json['id']
                #  self._json = json

    def _scrape_baseurl(self, baseurl):
        """
        :baseurl: url to scrape for immo data
        :returns: list of immos"""
        validate_url(baseurl)
        immobilien = []

        def scrape_JS(result_url):
            """ grab IS24.resultList variable from source code of url return IS24.resultList.resultListModel;
            the list of immobilien is in the key
            'IS24.resultList.resultListModel.searchResponseModel["resultlist.resultlist"].resultlistEntries[0].resultlistEntry'
            : [ immos,...] """

            if self.debug:
                assert isinstance(result_url, str)  # 'url is malformed'
            self._seleniumdriver.get(result_url.replace('http:', 'https:'))

            try:
                page_JS = self._seleniumdriver.execute_script(
                'return IS24.resultList.resultListModel.searchResponseModel["resultlist.resultlist"].resultlistEntries[0].resultlistEntry;')
            except Exception as e:
                print('Failed to scrape variable from url:',result_url,e)
            # if page only has one result page_JS is a dict, if it has many a list
            if isinstance(page_JS, list):
                pass
            elif isinstance(page_JS, dict):
                page_JS = [page_JS]
                if self.debug:
                    print('converting to list', page_JS[0]['@id'])
            elif page_JS is None:
                if self.debug:
                    print('the result page was empty ', page_JS)
                return []
            else:
                if self.debug:
                    print('no immobilie extracted from {0}, instead i got this?\n {1}, '.format(result_url, page_JS))
                return []

            for immo in page_JS:
                # add baseurl to dict
                immo['search_url'] = baseurl
            if self.debug:
                [print('extracted immobilie with id {0} from {1}'.format(imm['@id'], result_url))
                 for imm in page_JS]
            return page_JS

        next_page = baseurl
        while isinstance(next_page, str):
            immobilien.extend(scrape_JS(next_page))

            return immobilien
            try:
                next_page = self._seleniumdriver.find_element_by_link_text('nächste Seite')
                next_page = next_page.get_property('href')
                # recurse until no more pages for search are found
                if self.debug:
                    assert isinstance(next_page, str)
                    print('found next button, scrapeing subsequent page', next_page)
            except Exception as e:
                if self.debug:
                    print('no subsequent links found for', next_page)
                next_page = None
        return immobilien

    def _url2json(self, url, regexp='\{"results":(\[.+\])\},\n'):
        """scrapes script tags in a url for given regexp, describing json
        uses urllib as it ignores the JS, this is faster than rendering js with selenium/
        :url: list of urls to scrape
        :returns: list of dicts
        """
        import bs4
        import urllib5
        pattern = re.compile(regexp)
        resultjson = []
        html = urllib.request.urlopen(self._createRequest(url))
        soup = bs(html.read(), 'lxml')

        for script in soup.findAll('script'):
            data = pattern.findall(str(script.string))
            if len(data) > 0:
                for item in data:
                    resultjson.extend(json.loads(item))
        # add url to each dict
        resultjson = [dict(jsonitem, search_url=url) for jsonitem in resultjson]
        if self.debug:
            [print('scraped immobilie with id : {0} from '
                   'url:{1}, with {2} items'.format(jsonitem['id'],
                                                    url,
                                                    len(jsonitem)))
             for jsonitem in resultjson]
        return uniqDicts(resultjson, debug=self.debug)

    def dl_images(self, immo_id, gallerypictures):
        """download images
        :gallerypictures: list of dicts [ { "url" : ... ,"type":"..." },..]
        :returns:
        TODO: create absolute path to photos in rdbms"""
        assert isinstance(gallerypictures, list), 'is not of list type %r' % gallerypictures
        path = self.imagepath
        if not os.path.isdir(path):
            os.mkdir(path)
        #  pattern=re.compile(r'.+\/([0-9]+[-][0-9]+[.]jpg)\/.+')
        for i in range(0, len(gallerypictures)):
            filename = '{0}/{1}-{2}.jpg'.format(path, immo_id, i)
            url_to_dl = gallerypictures[i]['url']
            if not os.path.isfile(filename):
                if self.debug:
                    print('downloading :', url_to_dl, 'to :', filename)
                with open(filename, 'wb') as photo:
                    try:
                        photo.write(urllib.request.urlopen(url_to_dl).read())
                        photo.close()
                    except Exception as e:
                        print('url cant be found ', url_to_dl)
                        raise e
            else:
                print('file already exists:', filename)

def main(debug=False):
    """main"""
    import argparse

    def update_fotos():
        if parser.results['photo_dir'] is not [1]:
            if debugging:
                print('updating/downloading photos')
            image_urls = []
            if 'db' in locals():
                image_urls = db.conn.execute(select([db.immobilien.c.id,
                                                     db.immobilien.c.gallerypictures]))
                image_urls = [dict(id=d[0], gallerypictures=d[1])
                              for d in image_urls]
                assert isinstance(image_urls[0]['gallerypictures'], list), 'wrong type %r' % image_urls[0]['gallerypictures']
            if 'scrapeoff' not in locals():
                if isinstance(parser.results['photo_dir'], str):
                    scrapeoff = Immo_scraper(debug=debugging,
                                             imagepath=parser.results['photo_dir'])
                else:
                    scrapeoff = Immo_scraper(debug=debugging)
            try:
                image_urls.extend(scrapeoff.immobilien)
            except:
                print('no immobilie scraped, supply --url or --database parameter')
            image_urls = uniqDicts(image_urls)
            [scrapeoff.dl_images(dic['id'], dic['gallerypictures'])
             for dic in image_urls]

    parser = argparse.ArgumentParser(
        description='immoKrabbler, der Immobilienscout scraper')
    parser.add_argument('search', action="store_false", default=None)
    # db defaults to 0 if not supplied, None if suplied without value
    parser.add_argument('--database', nargs='?', const=1, type=str,
                        help='SqlAlchemy connection string, defaults to [sqlite:///immobilien.db]')
    # debug defaults to 0 if not supplied, None if suplied without value
    parser.add_argument('--debug', action="store_true", required=False,
                        help='debugging')
    parser.add_argument('--url', action="append", dest='url', nargs='+', required=False,
                        help='Immobilienscout search urls (space delimited)')
    parser.add_argument('--update-db', action="store_true", dest='update_db', required=False,
                        help='update search results in db')
    parser.add_argument('--json', action="store_true", dest='json', required=False,
                        help='write json to stdout')
    parser.add_argument('--photos', action="append", dest='photo_dir', nargs='?', const=1, required=False,
                        help='save photos to dir')
    parser.add_argument('--csv', action="store_true", dest='csv', required=False,
                        help='write csv to stdout')
    parser.add_argument('--outfile', action="append", dest='outfile', nargs='?', required=False,
                        help='write [csv|json] to file')
    parser.results = vars(parser.parse_args())
    debugging = False
    urls = []

    if parser.results['debug']:
        debugging = parser.results['debug']
        print('started debugging session ', datetime.datetime.utcnow())
        print('optargs :', parser.results)

    if isinstance(parser.results['url'], list):
        if debugging:
            print('urls supplied:', parser.results['url'])
        for url in [url for urllist in parser.results['url'] for url in urllist]:
            validate_url(url)
            urls.append(url)
        scrapeoff = Immo_scraper(urls=urls, debug=debugging)

    if parser.results['database'] or parser.results['update_db']:
        if isinstance(parser.results['database'], str):
            db = database(debug=debugging, db_uri=parser.results['database'])
        else:
            db = database(debug=debugging)

    if parser.results['update_db']:
        urls.extend(db.selectUniqeSearchUrls())
        urls = list(set(urls))
        if debugging:
            print('updating results for urls: ', urls)
        if 'scrapeoff' not in locals():
            scrapeoff = Immo_scraper(debug=debugging, urls=urls)
            # TODO:debug
            #  print('scraped nr of immos ', len(scrapeoff.immobilien))
            #  sys.exit(0)
        db.insertimmobilie(scrapeoff.immobilien)

    if parser.results['photo_dir']:
        update_fotos()
        # exit gracefully
        sys.exit(0)

    if 'url' not in locals() and parser.results['update_db'] is None:
        sys.exit('Scraper invoked without sane arguments')

    if parser.results['outfile'] is not None:
        if isinstance(parser.results['outfile'], str):
            outfile = parser.results['outfile']
        else:
            outfile = 'immobilien'
    else:
        outfile = sys.stdout

    if parser.results['csv'] is True:
        import csv
        if 'urls' not in locals():
            urls = []
        if 'scrapeoff' not in locals():
            scrapeoff = Immo_scraper(debug=debugging, urls=urls)
        if 'db' not in locals():
            db = database(debug=debugging, db_uri='sqlite:///:memory:')
        if len(urls) > 0:
            db.insertimmobilie(scrapeoff.immobilien)
        column_names = db.immobilien.__mapper__.columns
        selected = db.conn.execute(select([db.immobilien]))
        selected = [list(x) for x in selected]
        for row in selected:
            for col in row:
                col = str(col)
        if isinstance(outfile, str):
            with open(outfile, 'wb') as csvfile:
                print('writing csv to file:', csvfile)
                outcsv = csv.writer(csvfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL, lineterminator='\n')
                outcsv.writerows(selected)
                #  print(selected)
        else:
            outcsv = csv.writer(outfile, delimiter=';', quotechar='"', quoting=csv.QUOTE_ALL, lineterminator='\n')
            outcsv.writerows(selected)
        sys.exit(0)

    if parser.results['database'] is not None and len(urls) > 0:
        if debugging:
            print('scraping urls: ', urls)
        insertedImmobilien = db.insertimmobilie(scrapeoff.immobilien)
        print('scraped immobilien with ids: ', str([i['id'] for i in scrapeoff.immobilien]))
        try:
            print('inserted immobilien with ids: ', str([i for i in insertedImmobilien]))
        except:
            print('inserted 0 immobilien')
        # exit gracefully
        sys.exit(0)

    if 'urls' in locals() and len(urls) > 0 and parser.results['json'] is True:
        if debugging:
            print('scraped ', len(scrapeoff.immobilien), ' immobilien')

if __name__ == "__main__":
    # execute only if run as a script
    main()

# vim: set ts=4 sw=4 tw=79 expandtab foldclose=all foldenable foldmethod=indent :
