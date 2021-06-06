#!/usr/bin/python3
import configparser
import gettext
import gi
import locale
import os
import shutil
import string
import threading
import traceback
from gi.repository import GObject
from random import choice


#Arka planda işleri yürütmek için dekoratör olarak kullanılır
def _async(func):
    def wrapper(*args, **kwargs):
        thread = threading.Thread(target=func, args=args, kwargs=kwargs)
        thread.daemon = True
        thread.start()
        return thread
    return wrapper
#Ana döngüdeki şeyleri başka bir iş parçacığından çalıştırmak için bir dekoratör olarak kullanılır
def idle(func):
    def wrapper(*args):
        GObject.idle_add(func, *args)
    return wrapper

APP = 'quickly-web-manager'
LOCALE_DIR = "/usr/share/locale"
locale.bindtextdomain(APP, LOCALE_DIR)
gettext.bindtextdomain(APP, LOCALE_DIR)
gettext.textdomain(APP)
_ = gettext.gettext

#sabitler
ICE_DIR = os.path.expanduser("~/.local/share/ice")
APPS_DIR = os.path.expanduser("~/.local/share/applications")
PROFILES_DIR = os.path.join(ICE_DIR, "profiles")
FIREFOX_PROFILES_DIR = os.path.join(ICE_DIR, "firefox")
FIREFOX_FLATPAK_PROFILES_DIR = os.path.expanduser("~/.var/app/org.mozilla.firefox/data/ice/firefox")
EPIPHANY_PROFILES_DIR = os.path.join(ICE_DIR, "epiphany")
ICONS_DIR = os.path.join(ICE_DIR, "icons")
BROWSER_TYPE_FIREFOX, BROWSER_TYPE_FIREFOX_FLATPAK, BROWSER_TYPE_CHROMIUM, BROWSER_TYPE_EPIPHANY = range(4)

class Browser():

    def __init__(self, browser_type, name, exec_path, test_path):
        self.browser_type = browser_type
        self.name = name
        self.exec_path = exec_path
        self.test_path = test_path

#Uygulama menüsü öğesi (path, name, icon..etc.)
class WebAppLauncher():

    def __init__(self, path, codename):
        self.path = path
        self.codename = codename
        self.name = None
        self.icon = None
        self.is_valid = False
        self.exec = None
        self.category = None
        self.url = ""

        is_webapp = False
        with open(path) as desktop_file:
            for line in desktop_file:
                line = line.strip()

                # Uygulamanın bir web uygulaması olup olmadığını belirleyin
                if "StartupWMClass=WebApp" in line or "StartupWMClass=Chromium" in line or "StartupWMClass=ICE-SSB" in line:
                    is_webapp = True
                    continue

                if "Name=" in line:
                    self.name = line.replace("Name=", "")
                    continue

                if "Icon=" in line:
                    self.icon = line.replace("Icon=", "")
                    continue

                if "Exec=" in line:
                    self.exec = line.replace("Exec=", "")
                    continue

                if "Categories=" in line:
                    self.category = line.replace("Categories=", "").replace("GTK;", "").replace(";", "")
                    continue

                if "X-WebApp-URL=" in line:
                    self.url = line.replace("X-WebApp-URL=", "")
                    continue

        if is_webapp and self.name != None and self.icon != None:
            self.is_valid = True

#backend
#Yüklenecek yardımcı fonksiyonlar içerir,
#web uygulamalarını kaydet ve sil.
class QuicklyWebManager():

    def __init__(self):
        for directory in [ICE_DIR, APPS_DIR, PROFILES_DIR, FIREFOX_PROFILES_DIR, FIREFOX_FLATPAK_PROFILES_DIR, ICONS_DIR, EPIPHANY_PROFILES_DIR]:
            if not os.path.exists(directory):
                os.makedirs(directory)

    def get_webapps(self):
        webapps = []
        for filename in os.listdir(APPS_DIR):
            if filename.startswith("webapp-") and filename.endswith(".desktop"):
                path = os.path.join(APPS_DIR, filename)
                codename = filename.replace("webapp-", "").replace(".desktop", "")
                if not os.path.isdir(path):
                    try:
                        webapp = WebAppLauncher(path, codename)
                        if webapp.is_valid:
                            webapps.append(webapp)
                    except Exception:
                        print("Could not create webapp for path", path)
                        traceback.print_exc()

        return (webapps)

    def get_supported_browsers(self):
        browsers = []
        # tür, ad, yürütme, test
        browsers.append(Browser(BROWSER_TYPE_FIREFOX, "Firefox", "firefox", "/usr/bin/firefox"))
        browsers.append(Browser(BROWSER_TYPE_FIREFOX, "Firefox Developer Edition", "firefox-developer-edition", "/usr/bin/firefox-developer-edition"))
        browsers.append(Browser(BROWSER_TYPE_FIREFOX_FLATPAK, "Firefox (Flatpak)", "/var/lib/flatpak/exports/bin/org.mozilla.firefox", "/var/lib/flatpak/exports/bin/org.mozilla.firefox"))
        browsers.append(Browser(BROWSER_TYPE_CHROMIUM, "Brave", "brave-browser", "/usr/bin/brave-browser"))
        browsers.append(Browser(BROWSER_TYPE_CHROMIUM, "Chrome", "google-chrome", "/usr/bin/google-chrome-stable"))
        browsers.append(Browser(BROWSER_TYPE_CHROMIUM, "Chromium", "chromium", "/usr/bin/chromium"))
        browsers.append(Browser(BROWSER_TYPE_CHROMIUM, "Chromium (chromium-browser)", "chromium-browser", "/usr/bin/chromium-browser"))
        browsers.append(Browser(BROWSER_TYPE_CHROMIUM, "Chromium (Snap)", "chromium", "/snap/bin/chromium"))
        browsers.append(Browser(BROWSER_TYPE_EPIPHANY, "Epiphany", "epiphany", "/usr/bin/epiphany-browser"))
        browsers.append(Browser(BROWSER_TYPE_CHROMIUM, "Vivaldi", "vivaldi", "/usr/bin/vivaldi-stable"))
        browsers.append(Browser(BROWSER_TYPE_CHROMIUM, "Vivaldi Snapshot", "vivaldi-snapshot", "/usr/bin/vivaldi-snapshot"))
        browsers.append(Browser(BROWSER_TYPE_CHROMIUM, "Microsoft Edge", "microsoft-edge", "/usr/bin/microsoft-edge"))
        browsers.append(Browser(BROWSER_TYPE_CHROMIUM, "Ungoogled Chromium (Flatpak)", "/var/lib/flatpak/exports/bin/com.github.Eloston.UngoogledChromium", "/var/lib/flatpak/exports/bin/com.github.Eloston.UngoogledChromium"))
        browsers.append(Browser(BROWSER_TYPE_CHROMIUM, "Chromium (Flatpak)", "/var/lib/flatpak/exports/bin/org.chromium.Chromium", "/var/lib/flatpak/exports/bin/org.chromium.Chromium"))
        return browsers

    def delete_webbapp(self, webapp):
        shutil.rmtree(os.path.join(FIREFOX_PROFILES_DIR, webapp.codename), ignore_errors=True)
        shutil.rmtree(os.path.join(EPIPHANY_PROFILES_DIR, "/epiphany-%s" % webapp.codename), ignore_errors=True)
        shutil.rmtree(os.path.join(PROFILES_DIR, webapp.codename), ignore_errors=True)
        if os.path.exists(webapp.path):
            os.remove(webapp.path)

    def create_webapp(self, name, url, icon, category, browser, isolate_profile=True, navbar=False):
	    # 4 basamaklı rastgele bir kod oluşturalım (ad çakışmalarını önlemek için, böylece aynı ada sahip birden fazla başlatıcı tanımlayabiliriz)
        random_code =  ''.join(choice(string.digits) for _ in range(4))
        codename = "".join(filter(str.isalpha, name)) + random_code
        path = os.path.join(APPS_DIR, "webapp-%s.desktop" % codename)

        with open(path, 'w') as desktop_file:
            desktop_file.write("[Desktop Entry]\n")
            desktop_file.write("Version=1.0\n")
            desktop_file.write("Name=%s\n" % name)
            desktop_file.write("Comment=%s\n" % _("Web App"))

            if browser.browser_type in [BROWSER_TYPE_FIREFOX, BROWSER_TYPE_FIREFOX_FLATPAK]:
		# Firefox tabanlı
                firefox_profiles_dir = FIREFOX_PROFILES_DIR if browser.browser_type == BROWSER_TYPE_FIREFOX else FIREFOX_FLATPAK_PROFILES_DIR
                firefox_profile_path = os.path.join(firefox_profiles_dir, codename)
                desktop_file.write("Exec=sh -c 'FORCE_GTKWINDOW_ICON=" + icon + " " + browser.exec_path +
                                    " --class WebApp-" + codename +
                                    " --profile " + firefox_profile_path +
                                    " --no-remote " + url + "'\n")
		# Firefox profili oluşturalım
                shutil.copytree('/usr/share/web-manager/firefox/profile', firefox_profile_path)
                if navbar:
                    shutil.copy('/usr/share/web-manager/firefox/userChrome-with-navbar.css', os.path.join(firefox_profile_path, "chrome", "userChrome.css"))
            elif browser.browser_type == BROWSER_TYPE_EPIPHANY:
		# Epiphany tabanlı
                epiphany_profile_path = os.path.join(EPIPHANY_PROFILES_DIR, "epiphany-" + codename)
                desktop_file.write("Exec=" + browser.exec_path +
                                    " --application-mode " +
                                    " --profile=\"" + epiphany_profile_path + "\"" +
                                    " " + url + "\n")
            else:
		# Chromium tabanlı
                if isolate_profile:
                    profile_path = os.path.join(PROFILES_DIR, codename)
                    desktop_file.write("Exec=" + browser.exec_path +
                                        " --app=" + url +
                                        " --class=WebApp-" + codename +
                                        " --user-data-dir=" + profile_path + "\n")
                else:
                    desktop_file.write("Exec=" + browser.exec_path +
                                        " --app=" + url +
                                        " --class=WebApp-" + codename + "\n")

            desktop_file.write("Terminal=false\n")
            desktop_file.write("X-MultipleArgs=false\n")
            desktop_file.write("Type=Application\n")
            desktop_file.write("Icon=%s\n" % icon)
            desktop_file.write("Categories=GTK;%s;\n" % category)
            desktop_file.write("MimeType=text/html;text/xml;application/xhtml_xml;\n")
            desktop_file.write("StartupWMClass=WebApp-%s\n" % codename)
            desktop_file.write("StartupNotify=true\n")
            desktop_file.write("X-WebApp-URL=%s\n" % url)

            if browser.browser_type == BROWSER_TYPE_EPIPHANY:
		#Masaüstü dosyasını taşıyın ve bir sembolik link oluşturun
                new_path = os.path.join(epiphany_profile_path, "epiphany-%s.desktop" % codename)
                os.makedirs(epiphany_profile_path)
                os.replace(path, new_path)
                os.symlink(new_path, path)

    def edit_webapp(self, path, name, url, icon, category):
        config = configparser.RawConfigParser()
        config.optionxform = str
        config.read(path)
        config.set("Desktop Entry", "Name", name)
        config.set("Desktop Entry", "Icon", icon)
        config.set("Desktop Entry", "Comment", _("Web App"))
        config.set("Desktop Entry", "Categories", "GTK;%s;" % category)

        with open(path, 'w') as configfile:
            config.write(configfile, space_around_delimiters=False)
import sys
import urllib.error
import urllib.parse
import urllib.request
from PIL import Image
from io import BytesIO
import requests
import json

def normalize_url(url):
    (scheme, netloc, path, _, _, _) = urllib.parse.urlparse(url, "http")
    if not netloc and path:
        return urllib.parse.urlunparse((scheme, path, "", "", "", ""))
    return urllib.parse.urlunparse((scheme, netloc, path, "", "", ""))

def download_image(root_url, link):
    image = None
    if ("://") not in link:
        if link.startswith("/"):
            link = root_url + link
        else:
            link = root_url + "/" + link
    try:
        response = requests.get(link, timeout=3)
        image = Image.open(BytesIO(response.content))
        if image.height > 256:
            image = image.resize((256, 256), Image.BICUBIC)
    except Exception as e:
        print(e)
        print(link)
        image = None
    return image

import tempfile

def download_favicon(url):
    images = []
    url = normalize_url(url)
    (scheme, netloc, path, _, _, _) = urllib.parse.urlparse(url)
    root_url = "%s://%s" % (scheme, netloc)

    # önce favicon grabber deneyin		
    try:
        response = requests.get("https://favicongrabber.com/api/grab/%s?pretty=true" % netloc, timeout=3)
        if response.status_code == 200:
            source = response.content.decode("UTF-8")
            array = json.loads(source)
            for icon in array['icons']:
                image = download_image(root_url, icon['src'])
                if image != None:
                    t = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    images.append(["Favicon Grabber", image, t.name])
                    image.save(t.name)
        images = sorted(images, key = lambda x: (x[1].height), reverse=True)
        return images
    except Exception as e:
        print(e)

    #Fallback : HTML ile /favicon.ico' yu kontrol edin
    try:
        response = requests.get(url, timeout=3)
        if response != None:
            import bs4
            soup = bs4.BeautifulSoup(response.content, "html.parser")
	
            # HTML de tanımlanan simgeler
            for iconformat in ["apple-touch-icon", "shortcut icon", "icon", "msapplication-TileImage"]:
                item = soup.find("link", {"rel": iconformat})
                if item != None:
                    image = download_image(root_url, item["href"])
                    if image != None:
                        t = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                        images.append([iconformat, image, t.name])
                        image.save(t.name)

            # favicon.ico
            image = download_image(root_url, "/favicon.ico")
            if image != None:
                t = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                images.append(["favicon", image, t.name])
                image.save(t.name)  
            
	        # OG:IMAGE
            item = soup.find("meta", {"property": "og:image"})
            if item != None:
                image = download_image(root_url, item['content'])
                if image != None:
                    t = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
                    images.append(["og:image", image, t.name])
                    image.save(t.name)

    except Exception as e:
        print(e)

    images = sorted(images, key = lambda x: (x[1].height), reverse=True)
    return images

if __name__ == "__main__":
    download_favicon(sys.argv[1])    