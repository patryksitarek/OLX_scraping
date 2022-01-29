#!/usr/bin/env python
# coding: utf-8

# In[2]:


import requests
from bs4 import BeautifulSoup
import numpy as np
import pandas as pd
import smtplib, ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

#center column name in Pandas Dataframe
pd.set_option('colheader_justify', 'center')

class Olx_Scraper(object):
    '''
    Web scraper of polish version olx.pl (other versions not tested)
    
    Arguments:
    -------------------------------------
    required:
        url : [string] full link to search results (also with filters)
        
    not reqiured (especialy if you don't need notifications):
        send_notification : [bool] shuld also send mail notification
        notification_mail : [string] email address to which to send the notification
        num_send : [int] how many rows should be sent in mail notification
        num_follow : [int] how many rows should we compare if something changed since last scrap
                     (i.e. if ordered by price, mail will be sent only if 5 cheapest ads aren't the same as earlier)
        sender_mail : [string] mail address for your sender account (gmail compatible)
        sender_pass : [string] mail password for your sender account (gmail compatible)
    '''
    
    def __init__(self, url, send_notification = False, notification_mail = '', sender_mail = '', sender_pass = '', num_send = 5, num_follow = 5):
        '''Initialize variables'''
        self.url = url
        self.send_notification = send_notification
        self.notification_mail = notification_mail
        self.sender_mail = sender_mail
        self.sender_pass = sender_pass
        self.num_send = num_send
        self.num_follow = num_follow
        self.announ_found = 0
        self.data = []
        self.announs_old = []
        self.announs_new = []
                
    def scrap(self):
        titles = []
        prices = []
        deliveries = []
        locations = []
        announ_ids = []
        
        #get soup
        headers = {'User-Agent': 'Mozilla/5.0 (X11; Ubuntu; Linux x86_64; rv:79.0) Gecko/20100101 Firefox/79.0'}
        page = requests.get(self.url, headers = headers)
        soup = BeautifulSoup(page.content, 'html.parser')
        
        #check if any announcement found. If not just finish
        alert = str(soup.findAll('div', attrs = {'class' : 'emptynew large lheight18'}))
        if 'Nie znaleźliśmy ogłoszeń dla tego zapytania.' in alert:
            self.announ_found = 0
            return
        
        #get announcements
        announcements = soup.findAll('tr', attrs = {'class' : "wrap", 'rel' : ""})
        self.announ_found = len(announcements)
        
        for announ in announcements:
            #get title and price (in <strong> tags)
            result = announ.findAll('strong')
            #if len(result) == 1 there is title only, price is 0
            if len(result) == 1:
                titles.append(result[0].text)
                prices.append('0')
            else:
                title, price = result
                titles.append(title.text)
                prices.append(price.text)
            delivery = len(announ.findAll('div', attrs = {'class' : 'olx-delivery-icon'}))
            location = announ.findAll('small', attrs = {'class' : 'breadcrumb x-normal'})[1]
            location = location.findAll('span')[0]
            announ_id = announ.findAll('table')[0]['data-id']

            deliveries.append(bool(delivery))
            locations.append(location.text)
            announ_ids.append(int(announ_id))
        
        #format price table
        prices = self.format_price_table(prices)
        
        #concatenate in 2D array
        self.data = list(zip(titles, prices, deliveries, locations, announ_ids))
        
        #check if announs are new or still the same
        if self.send_notification is True:
            self.announs_new = announ_ids
            self.check_new_announs()
            
        return self.data
        
    def format_price_table(self, table):
        '''format price value: remove zł, spaces and set float'''
        table = np.char.strip(table, chars = [' zł'])
        table = np.core.defchararray.replace(table, ',', '.')
        table = np.char.replace(table, ' ', '')
        table = np.char.replace(table, 'Zamienię', '0').astype('float')
        return table
        
    def get_dataframe(self, data, columns = ['tytuł', 'cena', 'dostawa olx', 'lokalizacja', 'id'], order = 'cena'):
        '''get pandas dataframe from 2D array'''
        df = pd.DataFrame(data, columns = columns)
        df = df.sort_values(by = 'cena').reset_index(drop = True)
        df.head(n = 10)
        return df
    
    def check_new_announs(self):
        '''check if announs are new by ID'''
        if self.announs_old[:self.num_follow] == self.announs_new[:self.num_follow]:
            return
        self.announs_old = self.announs_new
        #send mail
        self.send_mail(self.sender_mail, self.sender_pass, self.notification_mail)
    
    def send_mail(self, login, password, receiver):
        port = 465  #SSL
        login = login
        password = password

        # Create a secure SSL context
        context = ssl.create_default_context()

        with smtplib.SMTP_SSL("smtp.gmail.com", port, context = context) as server:
            server.login(login, password)
            sender_email = login
            receiver_email = receiver

            message = MIMEMultipart("alternative")
            message["Subject"] = "OLX scraper"
            message["From"] = sender_email
            message["To"] = receiver_email

            #plain-text and HTML version of message
            header = 'Znalazłem nowe oferty!\n'
            df = self.get_dataframe(self.data)
            text = header + df[:self.num_send].to_string()
            html = header + df[:self.num_send].to_html()

            #turn into plain/html MIMEText objects
            part1 = MIMEText(text, "plain")
            part2 = MIMEText(html, "html")

            #add HTML/plain-text parts to MIMEMultipart message
            #the email client will try to render the last part first
            message.attach(part1)
            message.attach(part2)

            server.sendmail(sender_email, receiver_email, message.as_string())

