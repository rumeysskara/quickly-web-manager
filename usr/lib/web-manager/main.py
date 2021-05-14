#!/usr/bin/python3
import gettext
import gi
import locale
import os
import re
import setproctitle
import shutil
import subprocess
import tldextract
import warnings
import ThemedIconChooser

gi.require_version("Gtk", "3.0")

from gi.repository import Gtk, Gdk, Gio, GdkPixbuf, GLib

from common import _async, idle, QuicklyWebManager, Browser, download_favicon, ICONS_DIR, BROWSER_TYPE_FIREFOX

setproctitle.setproctitle("quickly-web-manager")

warnings.filterwarnings("ignore")

APP = 'quickly-web-manager'
LOCALE_DIR = "/usr/share/locale"
locale.bindtextdomain(APP, LOCALE_DIR)
gettext.bindtextdomain(APP, LOCALE_DIR)
gettext.textdomain(APP)
_ = gettext.gettext

COL_ICON, COL_NAME, COL_WEBAPP = range(3)
CATEGORY_ID, CATEGORY_NAME = range(2)
BROWSER_OBJ, BROWSER_NAME = range(2)

class MyApplication(Gtk.Application):
    # Ana başlatma rutini
    def __init__(self, application_id, flags):
        Gtk.Application.__init__(self, application_id=application_id, flags=flags)
        self.connect("activate", self.activate)

    def activate(self, application):
        windows = self.get_windows()
        if (len(windows) > 0):
            window = windows[0]
            window.present()
            window.show()
        else:
            window = QuicklyWebManagerWindow(self)
            self.add_window(window.window)
            window.window.show()

class QuicklyWebManagerWindow():

    def __init__(self, application):

        self.application = application
        self.settings = Gio.Settings(schema_id="org.x.quickly-web-manager")
        self.manager = QuicklyWebManager()
        self.selected_webapp = None
        self.icon_theme = Gtk.IconTheme.get_default()

        # Glade dosyasını ayarlayalım
        gladefile = "/usr/share/web-manager/web-manager.ui"
        self.builder = Gtk.Builder()
        self.builder.set_translation_domain(APP)
        self.builder.add_from_file(gladefile)
        self.window = self.builder.get_object("main_window")
        self.window.set_title(_("Quickly"))
        self.window.set_icon_name("web-manager")
        self.stack = self.builder.get_object("stack")
        self.icon_chooser = ThemedIconChooser.IconChooserButton()
        self.builder.get_object("icon_button_box").pack_start(self.icon_chooser, 0, True, True)
        self.icon_chooser.set_icon_contexts(["Applications"])
        self.icon_chooser.show_all()

        # Widget'lara hızlıca ulaşmak için değişkenleri oluşturalım
        self.headerbar = self.builder.get_object("headerbar")
        self.favicon_button = self.builder.get_object("favicon_button")
        self.add_button = self.builder.get_object("add_button")
        self.remove_button = self.builder.get_object("remove_button")
        self.edit_button = self.builder.get_object("edit_button")
        self.run_button = self.builder.get_object("run_button")
        self.ok_button = self.builder.get_object("ok_button")
        self.name_entry = self.builder.get_object("name_entry")
        self.url_entry = self.builder.get_object("url_entry")
        self.url_label = self.builder.get_object("url_label")
        self.spinner = self.builder.get_object("spinner")
        self.favicon_stack = self.builder.get_object("favicon_stack")
        self.browser_combo = self.builder.get_object("browser_combo")
        self.browser_label = self.builder.get_object("browser_label")

        # ekleme ssayfasında bulunan düzenleme sayfasında olmayan widgetlar
        self.add_specific_widgets = [self.browser_label, self.browser_combo]
        
        # Widget sinyali
        self.add_button.connect("clicked", self.on_add_button)
        self.builder.get_object("cancel_button").connect("clicked", self.on_cancel_button)
        self.builder.get_object("cancel_favicon_button").connect("clicked", self.on_cancel_favicon_button)
        self.remove_button.connect("clicked", self.on_remove_button)
        self.edit_button.connect("clicked", self.on_edit_button)
        self.run_button.connect("clicked", self.on_run_button)
        self.ok_button.connect("clicked", self.on_ok_button)
        self.favicon_button.connect("clicked", self.on_favicon_button)
        self.name_entry.connect("changed", self.on_name_entry)
        self.url_entry.connect("changed", self.on_url_entry)
        self.window.connect("key-press-event",self.on_key_press_event)
        

        # Menü çubuğu
        accel_group = Gtk.AccelGroup()
        self.window.add_accel_group(accel_group)
        menu = self.builder.get_object("main_menu")
        item = Gtk.ImageMenuItem()
        item.set_image(Gtk.Image.new_from_icon_name("preferences-desktop-keyboard-shortcuts-symbolic", Gtk.IconSize.MENU))
        item.set_label(_("Klavye kısayolları"))
        item.connect("activate", self.open_keyboard_shortcuts)
        key, mod = Gtk.accelerator_parse("<Control>K")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        menu.append(item)
        item = Gtk.ImageMenuItem()
        item.set_image(Gtk.Image.new_from_icon_name("help-about-symbolic", Gtk.IconSize.MENU))
        item.set_label(_("Hakkında"))
        item.connect("activate", self.open_about)
        key, mod = Gtk.accelerator_parse("F1")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        menu.append(item)
        item = Gtk.ImageMenuItem(label=_("Çıkış"))
        image = Gtk.Image.new_from_icon_name("application-exit-symbolic", Gtk.IconSize.MENU)
        item.set_image(image)
        item.connect('activate', self.on_menu_quit)
        key, mod = Gtk.accelerator_parse("<Control>Q")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        key, mod = Gtk.accelerator_parse("<Control>W")
        item.add_accelerator("activate", accel_group, key, mod, Gtk.AccelFlags.VISIBLE)
        menu.append(item)
        menu.show_all()

        #Ağaç görünümü
        self.treeview = self.builder.get_object("webapps_treeview")
        renderer = Gtk.CellRendererPixbuf()
        column = Gtk.TreeViewColumn("", renderer, pixbuf=COL_ICON)
        column.set_cell_data_func(renderer, self.data_func_surface)
        self.treeview.append_column(column)

        column = Gtk.TreeViewColumn("", Gtk.CellRendererText(), text=COL_NAME)
        column.set_sort_column_id(COL_NAME)
        column.set_resizable(True)
        self.treeview.append_column(column)
        self.treeview.show()
        self.model = Gtk.TreeStore(GdkPixbuf.Pixbuf, str, object) 
        self.model.set_sort_column_id(COL_NAME, Gtk.SortType.ASCENDING)
        self.treeview.set_model(self.model)
        self.treeview.get_selection().connect("changed", self.on_webapp_selected)
        self.treeview.connect("row-activated", self.on_webapp_activated)

        #Kategori kutusu
        category_model = Gtk.ListStore(str,str) 
        category_model.append(["Network",_("Internet")])
        category_model.append(["WebApps",_("Web uygulamaları")])
        category_model.append(["Utility",_("Donatılar")])
        category_model.append(["Game",_("Oyunlar")])
        category_model.append(["Graphics",_("Grafikler")])
        category_model.append(["Office",_("Ofis")])
        category_model.append(["AudioVideo",_("Ses & Video")])
        category_model.append(["Development",_("Programlama")])
        category_model.append(["Education",_("Eğitim")])
        self.category_combo = self.builder.get_object("category_combo")
        renderer = Gtk.CellRendererText()
        self.category_combo.pack_start(renderer, True)
        self.category_combo.add_attribute(renderer, "text", CATEGORY_NAME)
        self.category_combo.set_model(category_model)
        self.category_combo.set_active(0) # Kategori seçimi

        browser_model = Gtk.ListStore(object, str) 
        num_browsers = 0
        for browser in self.manager.get_supported_browsers():
            if os.path.exists(browser.test_path):
                browser_model.append([browser, browser.name])
                num_browsers += 1
        renderer = Gtk.CellRendererText()
        self.browser_combo.pack_start(renderer, True)
        self.browser_combo.add_attribute(renderer, "text", BROWSER_NAME)
        self.browser_combo.set_model(browser_model)
        self.browser_combo.set_active(0) # Tarayıcı seçimi
        if num_browsers == 0:
        	print ("Desteklenen tarayıcı bulunamadı.")
        	self.add_button.set_sensitive(False)
        	self.add_button.set_tooltip_text(_("Desteklenen tarayıcı bulunamadı."))
        if (num_browsers < 2):
            self.browser_label.hide()
            self.browser_combo.hide()
        self.browser_combo.connect("changed", self.on_browser_changed)

        self.load_webapps()
        
        # Tamam düğmesi ile kullanılır. Bir web uygulaması düzenlediğimizi yada yeni bir uygulama eklediğimizi gösterir.

        self.edit_mode = False

    def data_func_surface(self, column, cell, model, iter_, *args):
        pixbuf = model.get_value(iter_, COL_ICON)
        surface = Gdk.cairo_surface_create_from_pixbuf(pixbuf, self.window.get_scale_factor())
        cell.set_property("surface", surface)

    def open_keyboard_shortcuts(self, widget):
        gladefile = "/usr/share/web-manager/shortcuts.ui"
        builder = Gtk.Builder()
        builder.set_translation_domain(APP)
        builder.add_from_file(gladefile)
        window = builder.get_object("shortcuts-webappmanager")
        window.set_title(_("Quickly"))
        window.show()

    def open_about(self, widget):
        dlg = Gtk.AboutDialog()
        dlg.set_transient_for(self.window)
        dlg.set_title(_("Hakkında"))
        dlg.set_program_name(_("Quickly"))
        dlg.set_comments(_("Hızlı Web Yöneticisi"))
        try:
            h = open('/usr/share/common-licenses/GPL', encoding="utf-8")
            s = h.readlines()
            gpl = ""
            for line in s:
                gpl += line
            h.close()
            dlg.set_license(gpl)
        except Exception as e:
            print (e)

        dlg.set_icon_name("web-manager")
        dlg.set_logo_icon_name("web-manager")
        dlg.set_website("https://kod.pardus.org.tr/rumeysakara/quickly-web-manager")
        def close(w, res):
            if res == Gtk.ResponseType.CANCEL or res == Gtk.ResponseType.DELETE_EVENT:
                w.destroy()
        dlg.connect("response", close)
        dlg.show()

    def on_menu_quit(self, widget):
        self.application.quit()

    def on_webapp_selected(self, selection):
        model, iter = selection.get_selected()
        if iter is not None:
            self.selected_webapp = model.get_value(iter, COL_WEBAPP)
            self.remove_button.set_sensitive(True)
            self.edit_button.set_sensitive(True)
            self.run_button.set_sensitive(True)

    def on_webapp_activated(self, treeview, path, column):
        self.run_webapp(self.selected_webapp)

    def on_key_press_event(self, widget, event):
        ctrl = (event.state & Gdk.ModifierType.CONTROL_MASK)
        if ctrl and self.stack.get_visible_child_name() == "main_page":
            if event.keyval == Gdk.KEY_n:
                self.on_add_button(self.add_button)
            elif event.keyval == Gdk.KEY_e:
                self.on_edit_button(self.edit_button)
            elif event.keyval == Gdk.KEY_d:
                self.on_remove_button(self.remove_button)
        elif event.keyval == Gdk.KEY_Escape:
            self.load_webapps()

    def on_remove_button(self, widget):
        if self.selected_webapp != None:
            self.manager.delete_webbapp(self.selected_webapp)
            self.load_webapps()

    def run_webapp(self, webapp):
        if webapp != None:
            print("Running %s" % webapp.path)
            print("Executing %s" % webapp.exec)
            subprocess.Popen(webapp.exec, shell=True)

    def on_run_button(self, widget):
        self.run_webapp(self.selected_webapp)

    def on_ok_button(self, widget):
        category = self.category_combo.get_model()[self.category_combo.get_active()][CATEGORY_ID]
        browser = self.browser_combo.get_model()[self.browser_combo.get_active()][BROWSER_OBJ]
        name = self.name_entry.get_text()
        url = self.get_url()

        icon = self.icon_chooser.get_name()
        if "/tmp" in icon:
            # Simge yolu /tmp içindeyse taşıyın
            filename = "".join(filter(str.isalpha, name)) + ".png"
            new_path = os.path.join(ICONS_DIR, filename)
            shutil.copyfile(icon, new_path)
            icon = new_path
        if self.edit_mode:
            self.manager.edit_webapp(self.selected_webapp.path, name, url, icon, category)
            self.load_webapps()
        else:
            self.manager.create_webapp(name, url, icon, category, browser, )
            self.load_webapps()

    def on_add_button(self, widget):
        self.name_entry.set_text("")
        self.url_entry.set_text("")
        self.icon_chooser.set_name("web-manager")
        self.category_combo.set_active(0)
        self.browser_combo.set_active(0)
        self.show_hide_browser_widgets()
        self.stack.set_visible_child_name("add_page")
        self.headerbar.set_subtitle(_("Yeni bir uygulama ekle"))
        self.edit_mode = False
        self.toggle_ok_sensitivity()
        self.name_entry.grab_focus()

    def on_edit_button(self, widget):
        if self.selected_webapp != None:
            self.name_entry.set_text(self.selected_webapp.name)
            self.icon_chooser.set_name(self.selected_webapp.icon)
            self.url_entry.set_text(self.selected_webapp.url)
            model = self.category_combo.get_model()
            iter = model.get_iter_first()
            while iter:
                category = model.get_value(iter, CATEGORY_ID)
                if self.selected_webapp.category == category:
                    self.category_combo.set_active_iter(iter)
                    break
                iter = model.iter_next(iter)
            for widget in self.add_specific_widgets:
                widget.hide()
            self.stack.set_visible_child_name("add_page")
            self.headerbar.set_subtitle(_("Web uygulamasını düzenle"))
            self.edit_mode = True
            self.toggle_ok_sensitivity()
            self.name_entry.grab_focus()

    def on_cancel_button(self, widget):
        self.load_webapps()

    def on_cancel_favicon_button(self, widget):
        self.stack.set_visible_child_name("add_page")
        self.headerbar.set_subtitle(_("Yeni bir uygulama ekle"))

    def on_favicon_button(self, widget):
        url = self.get_url()
        self.spinner.start()
        self.spinner.show()
        self.favicon_stack.set_visible_child_name("page_spinner")
        self.favicon_button.set_sensitive(False)
        self.download_icons(url)

    # URL girişinin içindekileri okur ve doğrulanmış bir sürümü döndürür
    def get_url(self):
        url = self.url_entry.get_text().strip()
        if url == "":
            return ""
        if not "://" in url:
            url = "http://%s" % url
        return url

    @_async
    def download_icons(self, url):
        images = download_favicon(url)
        self.show_favicons(images)

    @idle
    def show_favicons(self, images):
        self.spinner.stop()
        self.spinner.hide()
        self.favicon_stack.set_visible_child_name("page_image")
        self.favicon_button.set_sensitive(True)
        if len(images) > 0:
            self.stack.set_visible_child_name("favicon_page")
            self.headerbar.set_subtitle(_("Bir simge seçin"))
            box = self.builder.get_object("favicon_flow")
            for child in box.get_children():
                box.remove(child)
            for origin, pil_image, path in images:
                button = Gtk.Button()
                content_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
                image = Gtk.Image()
                image.set_from_file(path)
                dimensions = Gtk.Label()
                dimensions.set_text("%dx%d" % (pil_image.width, pil_image.height))
                source = Gtk.Label()
                source.set_text(origin)
                content_box.pack_start(image, 0, True, True)
                # content_box.pack_start(source, 0, True, True)
                content_box.pack_start(dimensions, 0, True, True)
                button.add(content_box)
                button.connect("clicked", self.on_favicon_selected, path)
                box.add(button)
            box.show_all()

    def on_favicon_selected(self, widget, path):
        self.icon_chooser.set_name(path)
        self.stack.set_visible_child_name("add_page")
        self.headerbar.set_subtitle(_("Add a New Web App"))

    def on_browser_changed(self, widget):
        self.show_hide_browser_widgets()

    def show_hide_browser_widgets(self):
        browser = self.browser_combo.get_model()[self.browser_combo.get_active()][BROWSER_OBJ]

    def on_name_entry(self, widget):
        self.toggle_ok_sensitivity()

    def on_url_entry(self, widget):
        if self.get_url() != "":
            self.favicon_button.set_sensitive(True)
        else:
            self.favicon_button.set_sensitive(False)
        self.toggle_ok_sensitivity()
        self.guess_icon()

    def toggle_ok_sensitivity(self):
        if self.name_entry.get_text() == "" or self.get_url() == "":
            self.ok_button.set_sensitive(False)
        else:
            self.ok_button.set_sensitive(True)

    def guess_icon(self):
        url = self.get_url().lower()
        if url != "":
            info = tldextract.extract(url)
            icon = None
            if info.domain == None or info.domain == "":
                return
            if info.domain == "google" and info.subdomain != None and info.subdomain != "":
                if info.subdomain == "mail":
                    icon = "web-%s-gmail" % info.domain
                else:
                    icon = "web-%s-%s" % (info.domain, info.subdomain)
            elif info.domain == "gmail":
                icon = "web-google-gmail"
            elif info.domain == "youtube":
                icon = "web-google-youtube"
            if icon != None and self.icon_theme.has_icon(icon):
                self.icon_chooser.set_name(icon)
            elif self.icon_theme.has_icon("web-%s" % info.domain):
                self.icon_chooser.set_name("web-%s" % info.domain)
            elif self.icon_theme.has_icon(info.domain):
                self.icon_chooser.set_name(info.domain)

    def load_webapps(self):
        # Ağaç görünümünü ve seçimi temizleyelim
        self.model.clear()
        self.selected_webapp = None
        self.remove_button.set_sensitive(False)
        self.edit_button.set_sensitive(False)
        self.run_button.set_sensitive(False)

        webapps = self.manager.get_webapps()
        for webapp in webapps:
            if webapp.is_valid:
                if "/" in webapp.icon and os.path.exists(webapp.icon):
                    pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_size(webapp.icon, -1, 32 * self.window.get_scale_factor())
                else:
                    if self.icon_theme.has_icon(webapp.icon):
                        pixbuf = self.icon_theme.load_icon(webapp.icon, 32 * self.window.get_scale_factor(), 0)
                    else:
                        pixbuf = self.icon_theme.load_icon("web-manager", 32 * self.window.get_scale_factor(), 0)

                iter = self.model.insert_before(None, None)
                self.model.set_value(iter, COL_ICON, pixbuf)
                self.model.set_value(iter, COL_NAME, webapp.name)
                self.model.set_value(iter, COL_WEBAPP, webapp)

        # ilk web uygulamasını seçelim
        path = Gtk.TreePath.new_first()
        self.treeview.get_selection().select_path(path)

        # Ana sayfaya geç
        self.stack.set_visible_child_name("main_page")
        self.headerbar.set_subtitle(_("Hızlı Web Yöneticisi"))


if __name__ == "__main__":
    application = MyApplication("org.x.quickly-web-manager", Gio.ApplicationFlags.FLAGS_NONE)
    application.run()

