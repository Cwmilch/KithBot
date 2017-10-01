import os
from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as ec
from lxml import etree
from time import sleep
import http.client as client
from urllib import request

product_xml_main = None
product_xml_backup = None
working_link = None
parser = etree.XMLParser(ns_clean=True, remove_comments=True, recover=True, encoding='utf-8')


def init():
    chrome_driver = "chromedriver.exe"
    os.environ["webdriver.chrome.driver"] = chrome_driver
    chrome_options = webdriver.ChromeOptions()

    # Directory of chrome files to use - used separate chrome settings with pictures disabled to load pages faster
    chrome_options.add_argument('user-data-dir=chrome')
    browser = webdriver.Chrome(chrome_driver, chrome_options=chrome_options)
    return browser


# Load billing/shipping info from Info.txt
def parse_info():
    max_size = 1000  # Limit file input size when reading to prevent memory overflow, shouldn't need more than 1k bytes
    file = open('Info.txt').read(max_size).rstrip().split('\n')
    file_info = {}
    for i in range(0, file.__len__()):
        data = file[i].split(':')
        key = data[0]
        value = data[1]
        file_info[key] = value[1:] if value[0] == ' ' else value
    return file_info


# Try to predict the link the website uses, rather than repeatedly loading and iterating through the home page
def find_link():
    global working_link

    # If a working link hasn't already been found, look for one
    if working_link is None:
        # Array of links to check, wasn't sure what the url would be
        links = ['/collections/kith-x-coca-cola-summer-2017-capsule', '/collections/kith-x-coca-cola-summer-2017',
                 '/collections/kith-x-coca-cola-summer', '/collections/kith-classics-laguardia-program']
        # Use header from chrome so HTTPSConnection isn't blocked
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
                                 'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/60.0.3112.90 Safari/537.36'}
        count = 0

        while working_link is None:
            count = count + 1
            for link in links:
                conn = client.HTTPSConnection('kith.com')
                conn.request("HEAD", link, headers=headers)
                if not str(conn.getresponse().status) == '404':
                    working_link = 'https://kith.com' + link
                    return working_link
            # Check Dropbox file where I'd upload a different link if all of the link predictions were wrong
            for line in request.urlopen('https://www.dropbox.com/s/uc31sp04ve0tect/dropbox%20code.txt?dl=1'):
                code = str(line, 'utf-8')
                if not code == 'Unknown':
                    working_link = code
                    return working_link
                else:
                    sleep(3)  # Wait before trying again to avoid being blocked for excessive requests
    else:
        return working_link


# Get the XML data for a specific item
def get_xml(browser, backup):
    browser.get(find_link())
    item_list = browser.find_elements_by_class_name('product-card-info')
    links = []
    for item in item_list:
        # Iterate through all clothing items, try to find one with predicted link
        link = item.get_attribute('href')
        # If trying to buy the first item hasn't already failed, look for its link
        if (not backup) and ('converse' in link
                             or 'chuck-taylor' in link
                             or 'all-star' in link
                             or '-70-' in link
                             or 'sneaker' in link
                             or 'allstar' in link
                             or 'tee-pink' in link):
            browser.get(link + '.xml')
            source = browser.page_source
            index = source.find('<hash>')
            # Return the XML info for the item, trim any excess formatting in the beginning by starting at actual XML
            return source[index:]
        # If the first item was sold out or the link was guessed wrong, try for the secondary item
        elif backup:
            if 'tee-black' in link:
                links.append(link)
    if backup:
        for link in links:
            # Make sure it's the right item
            if 'raglan' in link:
                browser.get(link + '.xml')
                source = browser.page_source
                index = source.find('<hash>')
                return source[index:]


# Search for the item's Shopify ID in it's XML page
def find_product_id(browser, sold, backup):
    if not backup:
        global product_xml_main
        xml_value = product_xml_main
    else:
        global product_xml_backup
        xml_value = product_xml_backup

    # Store product XML in variable to avoid repeatedly searching for it
    if xml_value is None:
        xml_value = get_xml(browser, backup).replace('\n', '').encode('utf-8')
        if not backup:  # If the program is trying to buy the first item, save the xml to product_xml_main
            product_xml_main = xml_value
        else:  # Save the xml to product_xml_backup if the program is trying to buy the backup item
            product_xml_backup = xml_value
    tree = etree.fromstring(xml_value, parser)
    if not backup:
        size = 'S' if not sold else 'L'
    else:
        size = 'S' if not sold else 'M'

    # Use xpath selector to find the Shopify ID associated with the specific size of the item
    return str(tree.xpath('//title[text()=\'' + str(size) + '\']/parent::variant/child::*[1]/text()')[0])


# Run javascript to fill text field, faster than having Selenium stimulate typing
def fill_field(browser, elem_id, val):
    script = 'document.getElementById(\'' + elem_id + '\').value="' + val + '"'
    browser.execute_script(script)


# Fill in shipping info
def fill_shipping(browser):
    # Get the shipping info loaded from Info.txt
    email = info['Email']

    name = info['Name'].split(' ')
    first = name[0]
    second = name[1]

    address = info['Address']
    city = info['City']
    zipcode = info['ZIP Code']
    phone = info['Phone']

    # If the item is sold out when trying to check out, try a secondary size
    browser.get('http://shop.kithnyc.com/cart/' + find_product_id(browser, False, False) + ':1')
    check = browser.find_element_by_class_name('section__title')
    if check.text == 'Inventory issues':
        browser.get('http://shop.kithnyc.com/cart/' + find_product_id(browser, True, False) + ':1')
        check = browser.find_element_by_class_name('section__title')

        # If the secondary size is sold out, repeat the process with another item
        if check.text == 'Inventory issues':
            browser.get('http://shop.kithnyc.com/cart/' + find_product_id(browser, False, True) + ':1')
            check = browser.find_element_by_class_name('section__title')
            if check.text == 'Inventory issues':
                browser.get('http://shop.kithnyc.com/cart/' + find_product_id(browser, True, False) + ':1')

    fill_field(browser, 'checkout_email', email)

    fill_field(browser, 'checkout_shipping_address_first_name', first)

    fill_field(browser, 'checkout_shipping_address_last_name', second)

    fill_field(browser, 'checkout_shipping_address_city', city)

    fill_field(browser, 'checkout_shipping_address_zip', zipcode)

    fill_field(browser, 'checkout_shipping_address_phone', phone)

    fill_field(browser, 'checkout_shipping_address_address1', address)

    browser.execute_script('document.getElementsByName("button")[0].click()')

    # Wait for shipping options to load, make sure an option was selected before proceeding to the next page
    # Typically only one choice for shipping, no need to look for specific option
    shipping_button = WebDriverWait(browser, 30).until(ec.visibility_of_element_located
                                                       ((By.CLASS_NAME, "input-radio")))
    shipping_button.submit()

    elem = browser.find_element_by_class_name("step__footer__continue-btn")
    elem.submit()


# Fill in credit card info
def fill_billing(browser):
    card_num = info['Credit Card Number']
    card_name = info['Name on Card']
    card_date = info['Expiration Date (mm/yy)']
    card_code = info['Security Code']

    # Enter credit card info as single string, use \t to switch between fields
    cc = card_num + '\t' + card_name + '\t' + card_date + '\t' + card_code

    # Credit card field is an iframe, have to switch to it to be able to enter info
    browser.switch_to_frame(browser.find_element_by_xpath('//iframe[@class = "card-fields-iframe"]'))
    browser.find_element_by_xpath('//input[@autocomplete = "cc-number"]').send_keys(cc)


def purchase(browser):
    fill_shipping(browser)
    fill_billing(browser)


info = parse_info()
chrome_browser = init()

purchase(chrome_browser)
