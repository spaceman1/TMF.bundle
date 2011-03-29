import base64, re, string

####################################################################################################

PLUGIN_TITLE = "TMF"
PLUGIN_PREFIX = "/video/tmf"

TMF_BASE_URL = "http://www.tmf.nl"
TMF_CONTENT = "%s/ajax/?letterResults=%%s" % TMF_BASE_URL
TMF_ARTISTS_QUERY = "type=artists&static=true&letter=%s&pagina=%d&m=common/alphabetic_list"
TMF_ARTIST_PAGE = "%s/artiesten/%%s/" % TMF_BASE_URL
TMF_ARTIST_VIDEOS = "%s/xml/videoplayer/related.php?id=%%s&action=all" % TMF_BASE_URL
TMF_VIDEO_INFO = "%s/xml/videoplayer/mrss.php?uri=mgid:nlcms:video:tmf.nl:%%s" % TMF_BASE_URL

# RSS feed with TV stream info
TMF_TV_STREAMS_FEED = "http://pipes.yahoo.com/pipes/pipe.run?_id=woCrdodv3hG3mPCcwmH_9A&_render=rss"

# Plex webplayer for RTMP streams
PLEXAPP_RTMP_PLAYER_URL = "http://www.plexapp.com/player/player.php?url=%s&clip=%s"

CACHE_INTERVAL = CACHE_1DAY

# Default artwork and icon(s)
PLUGIN_ARTWORK = "art-default.png"
PLUGIN_ICON_DEFAULT = "icon-default.png"

####################################################################################################

def Start():
  Plugin.AddPrefixHandler(PLUGIN_PREFIX, MainMenu, L("PLUGIN_TITLE"))
  Plugin.AddViewGroup("List", viewMode="List", mediaType="items")

  # Set the default MediaContainer attributes
  MediaContainer.title1         = L("PLUGIN_TITLE")
  MediaContainer.viewGroup      = "List"
  MediaContainer.art            = R(PLUGIN_ARTWORK)

  # Set the default cache time
  HTTP.SetCacheTime(CACHE_INTERVAL)

####################################################################################################

def MainMenu():
  dir = MediaContainer(noCache=True)

  if Prefs['showtvstreams']:
    dir.Append(Function(DirectoryItem(TvStreams, title=L("TITLE_TV_STREAMS"), thumb=R(PLUGIN_ICON_DEFAULT))))
  if Prefs['showvideoclips']:
    dir.Append(Function(DirectoryItem(VideoClipsAtoZ, title=L("TITLE_VIDEO_CLIPS"), thumb=R(PLUGIN_ICON_DEFAULT))))
  dir.Append(PrefsItem(L("TITLE_PREFERENCES"), thumb=R(PLUGIN_ICON_DEFAULT)))

  return dir

####################################################################################################

def TvStreams(sender):
  dir = MediaContainer(title2=L("TITLE_TV_STREAMS"))

  feed = XML.ElementFromURL(TMF_TV_STREAMS_FEED, errors='ignore').xpath('//channel/item')

  for item in feed:
    url   = item.xpath('./link')[0].text
    title = item.xpath('./title')[0].text
    thumb = item.xpath('./enclosure')[0].get('url')

    dir.Append(WebVideoItem(url=url, title=title, thumb=thumb))

  return dir

####################################################################################################

def VideoClipsAtoZ(sender):
  dir = MediaContainer(title2=L("TITLE_VIDEO_CLIPS"))

  # A to Z
  for char in string.ascii_uppercase:
    dir.Append(Function(DirectoryItem(Artists, title=char, thumb=R(PLUGIN_ICON_DEFAULT)), letter=char))

  # 0-9
  dir.Append(Function(DirectoryItem(Artists, title='0-9', thumb=R(PLUGIN_ICON_DEFAULT)), letter='0-9'))

  return dir

####################################################################################################

def Artists(sender, letter):
  dir = MediaContainer(title1=L("TITLE_VIDEO_CLIPS"), title2=letter)

  query = base64.b64encode(TMF_ARTISTS_QUERY % (letter.lower(), 1))
  content = HTML.ElementFromURL(TMF_CONTENT % query, errors='ignore')

  # Number of pages for this letter
  pages = content.xpath('//div[@class="cb"]/a')
  # Pagination is displayed twice on the page if there's more than 1 page, so we need to divide by 2.
  # The -1 is needed because of the 'last page' link.
  numPages = 1 if len(pages) == 0 else len(pages)/2-1

  for i in range(1, numPages+1):
    query = base64.b64encode(TMF_ARTISTS_QUERY % (letter.lower(), i))
    content = HTML.ElementFromURL(TMF_CONTENT % query, errors='ignore').xpath('//div[@class="cb item"]')

    for item in content:
      id = item.xpath('./div[@class="title"]/a')[0].get('href').split('/')[2]
      artist = item.xpath('./div[@class="title"]/a')[0].text.strip()

      if Prefs['showhiresthumbs']:
        thumb = HTML.ElementFromURL(TMF_ARTIST_PAGE % id, errors='ignore').xpath('//div[@class="groupPhotoMain"]')[0].get('style')
        thumb = re.search(r'url\((.+)\);', thumb).group(1)
      else:
        # Find lo-res thumbs
        thumb = item.xpath('.//img[@class="ib"]')[0].get('src')

      dir.Append(Function(DirectoryItem(Videos, title=artist, thumb=thumb), id=id, artist=artist))

  return dir

####################################################################################################

def Videos(sender, id, artist):
  dir = MediaContainer(title1=L("TITLE_VIDEO_CLIPS"), title2=artist)

  content = HTTP.Request(TMF_ARTIST_VIDEOS % id)
  if len(content) > 100:
    content = XML.ElementFromString(content).xpath('//content/image')

    for item in content:
      videoId = item.xpath('./data')[0].text
      videoId = re.search(r'Video\((.+)\);', videoId).group(1)

      title = item.xpath('./description')[0].text
      if title.find(" - ") != -1:
        title = title.split(" - ", 1)[1]

      screenshot = item.xpath('./path')[0].text.split("proxy.php?src=", 1)[1]

      dir.Append(Function(WebVideoItem(PlayVideo, title=title, thumb=screenshot), videoId=videoId))

  return dir

####################################################################################################

def PlayVideo(sender, videoId):
  content = HTTP.Request(TMF_VIDEO_INFO % videoId)
  if len(content) > 100:
    # Changed xpath to a regex because the xml file sometimes isn't valid due to unencoded ampersands in text like "R&B" (and xpath fails)
    # link = XML.ElementFromString(content).xpath('//media:content', namespaces={'media':'http://search.yahoo.com/mrss/'})[0].get('url')
    link = re.search('<media:content.+?url="(.+?)">', content).group(1)
    videoSrc = XML.ElementFromURL(link, errors='ignore').xpath('//rendition[src!=""]/src')[0].text

    if videoSrc.find("edgefcs") != -1:
      (streamer,file) = videoSrc.split('/ondemand/')
      streamer = streamer + "/ondemand"
      file = file.split('?', 1)[0] # Lose the ?llnwd.net at the end of the string if it's there (why is it there in the first place?!?)
      if file.find('.mp4') != -1:
        file = 'mp4:' + file[:-4]
      elif file.find('.flv') != -1:
        file = file[:-4]
      url = (PLEXAPP_RTMP_PLAYER_URL % (streamer,file))
    elif videoSrc.find("llnwd") != -1:
      partUrl = re.search('rtmp://(.+)\.flv', videoSrc).group(1)
      partUrl = partUrl.rsplit('/', 1)
      streamer = 'rtmp://' + partUrl[0]
      file = partUrl[1]
      url = (PLEXAPP_RTMP_PLAYER_URL % (streamer,file))

    return Redirect('plex://localhost/video/:/webkit?url=' + String.Quote(url, usePlus=True))
  else:
    return None
