#!/usr/bin/env python3
r"""
This script will update a cloudflare dns entry
with the current external ip address
"""

import sys
import CloudFlare
import requests
import configparser


def my_ip_address():
    # TODO: Make this a setting
    ip_lookup_service = 'https://api.ipify.org'
    try:
        ip_address = requests.get(ip_lookup_service).text
    except:
        exit('%s: failed' % (ip_lookup_service))

    if ip_address == '':
        exit('%s: failed' % (ip_lookup_service))

    return ip_address


def do_dns_update(token, dns_name, ip_address):
    cf = CloudFlare.CloudFlare(token=token)

    host_name, zone_name = '.'.join(dns_name.split('.')[:2]), '.'.join(dns_name.split('.')[-2:])

    # grab the zone identifier
    try:
        params = {'name': zone_name}
        zones = cf.zones.get(params=params)
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        exit('/zones %d %s - api call failed' % (e, e))
    except Exception as e:
        exit('/zones.get - %s - api call failed' % (e))

    if len(zones) == 0:
        exit('/zones.get - %s - zone not found' % (zone_name))

    if len(zones) != 1:
        exit('/zones.get - %s - api call returned %d items' % (zone_name, len(zones)))

    zone = zones[0]

    zone_id = zone['id']

    if ':' in ip_address:
        ip_address_type = 'AAAA'
    else:
        ip_address_type = 'A'
    try:
        params = {'name': dns_name, 'match': 'all', 'type': ip_address_type}
        dns_records = cf.zones.dns_records.get(zone_id, params=params)
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        exit('/zones/dns_records %s - %d %s - api call failed' % (dns_name, e, e))

    updated = False

    # update the record - unless it's already correct
    for dns_record in dns_records:
        old_ip_address = dns_record['content']
        old_ip_address_type = dns_record['type']

        if ip_address_type not in ['A', 'AAAA']:
            # we only deal with A / AAAA records
            continue

        if ip_address_type != old_ip_address_type:
            # only update the correct address type (A or AAAA)
            # we don't see this because of the search params above
            print('IGNORED: %s %s ; wrong address family' % (dns_name, old_ip_address))
            continue

        if ip_address == old_ip_address:
            print('UNCHANGED: %s %s' % (dns_name, ip_address))
            updated = True
            continue

        proxied_state = dns_record['proxied']

        # Yes, we need to update this record - we know it's the same address type

        dns_record_id = dns_record['id']
        dns_record = {
            'name': dns_name,
            'type': ip_address_type,
            'content': ip_address,
            'proxied': proxied_state
        }
        try:
            dns_record = cf.zones.dns_records.put(zone_id, dns_record_id, data=dns_record)
        except CloudFlare.exceptions.CloudFlareAPIError as e:
            exit('/zones.dns_records.put %s - %d %s - api call failed' % (dns_name, e, e))
        print('UPDATED: %s %s -> %s' % (dns_name, old_ip_address, ip_address))
        updated = True

    if updated:
        return

    # no existing dns record to update - so create dns record
    dns_record = {
        'name': dns_name,
        'type': ip_address_type,
        'content': ip_address
    }
    try:
        dns_record = cf.zones.dns_records.post(zone_id, data=dns_record)
    except CloudFlare.exceptions.CloudFlareAPIError as e:
        exit('/zones.dns_records.post %s - %d %s - api call failed' % (dns_name, e, e))
    print('CREATED: %s %s' % (dns_name, ip_address))


def write_config(config):
    with open('settings.ini', 'w') as configfile:
        config.write(configfile)


def main():
    config = configparser.ConfigParser()
    config.read('settings.ini')

    settings = {
        'url': config.get('CloudFlare', 'url', fallback='my-home.example.com'),
        'cloudflare_api_token': config.get('CloudFlare', 'cloudflare_api_token', fallback=''),
        'proxied': config.get('CloudFlare', 'proxied', fallback='false'),
        'most_recent_ip': config.get('CloudFlare', 'most_recent_ip', fallback='0.0.0.0')
    }

    if settings['cloudflare_api_token'] == '':
        config['CloudFlare'] = settings
        write_config(config)
        exit('error: update settings.ini to use your cloudflare token')

    settings['url'] = settings['url']

    ip_address = my_ip_address()

    print('MY IP: %s %s' % (settings['url'], ip_address))

    if settings['most_recent_ip'] == ip_address:
        print("IP hasn't changed since last run")
        exit(0)

    settings['most_recent_ip'] = ip_address

    do_dns_update(settings['cloudflare_api_token'], settings['url'], ip_address)

    config['CloudFlare'] = settings
    write_config(config)

    exit(0)


if __name__ == '__main__':
    main()
