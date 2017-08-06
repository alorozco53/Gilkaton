#! /usr/bin/env python
# -*- coding: utf-8 -*-

from __future__ import absolute_import
from __future__ import division
from __future__ import print_function

from docx import Document
import re
import csv
import nltk
import argparse

months = ['(enero)',
          '(febrero)',
          '(marzo)',
          '(abril)',
          '(mayo)',
          '(junio)',
          '(julio)',
          '(agosto)',
          '(septiembre)',
          '(octubre)',
          '(noviembre)',
          '(diciembre)']

hundreds = ['cien',
            'doscientos',
            'trescientos',
            'cuatrocientos',
            'quinientos',
            'seiscientos',
            'setecientos',
            'ochocientos',
            'novecientos']
units = []
ones = []
day_regex = '(primero)|(veinte)|(treinta)'
num_map = {
    '(primero)': '1',
    '(veinte)': '20',
    '(treinta)': '30'
}
with open('0s.txt', 'r') as f:
    for num, line in enumerate(f):
        val1 = '({})'.format(line.strip())
        val2 = '(veinti{})'.format(line.strip())
        units.append(val1)
        units.append(val2)
        num_map[val1] = str(num + 1)
        num_map[val2] = '2{}'.format(str(num + 1))
        if line in ['uno', 'dos']:
            val3 = '(treinta y {})'.format(line.strip())
            units.append(val3)
            num_map[val3] = '3{}'.format(str(num + 1))
day_regex += '|' + '|'.join(units)
with open('1s.txt', 'r') as f:
    for num, line in enumerate(f):
        val = '({})'.format(line.strip())
        ones.append(val)
        num_map[val] = '1{}'.format(str(num + 1))
day_regex += '|' + '|'.join(ones)
day_regex = re.compile(day_regex)


def ctx_sentence(para, regex):
    """
     Returns each sentence where the given regex is found
     text := [string]
    """
    p = re.sub('C\.', 'C', para)
    sents = [w.strip() for w in re.split('[\.?!;]', p)]
    for s in sents:
        match = regex.search(s)
        if match:
            return re.sub('\\bC\\b', 'C.', s)
    return para

def to_digits(text, mode):
    assert mode in ['day', 'month', 'year']
    if mode == 'day':
        try:
            match = day_regex.search(text)
            if match:
                t = match.group()
                conv = num_map['({})'.format(t)]
                return conv
            else:
                return text
        except KeyError:
            return text
    elif mode == 'month':
        for num, m in enumerate(months):
            month = '({})'.format(text)
            if m == month:
                mn = str(num + 1)
                if len(mn) < 2:
                    return '0{}'.format(mn)
                else:
                    return mn
        return ''
    elif mode == 'year':
        spl = text.split()
        if text.startswith('dos'):
            conv = '2'
            spl = spl[1:]
        else:
            conv = '1'
        for part in spl:
            match = day_regex.search(part)
            if match:
                case = '({})'.format(part)
                if conv and conv[-1] in ['9', '0'] and int(num_map[case]) < 10:
                    conv += '0{}'.format(num_map[case])
                else:
                    conv += num_map[case]
            elif part == 'mil':
                conv += '0'
            elif part in hundreds:
                conv += str(hundreds.index(part) + 1)
        return conv

def date_parser(text):
    day = ''
    month = ''
    year = ''
    splitted = [w.strip() for w in re.split('del?', text)]
    for word in splitted:
        day_match = re.search('\\b([123](o?\.?))?[0-9]\\b', word)
        if day_match:
            day = day_match.group()
        month_match = re.search('%s' % '|'.join(months), word)
        if month_match:
            month = month_match.group()
            month = to_digits(month, mode='month')
        year_match = re.search('[0-9]{4}', word)
        if year_match:
            year = year_match.group()
    if not day:
        day = to_digits(splitted[0], mode='day')
    if not year:
        year = to_digits(splitted[2], mode='year')
    return '/'.join([day, month, year])

def entidades(paragraphs):
    ctx_regex = re.compile('(el|la|El|La) [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+ [A-ZÁÉÍÓÚÑ][a-záéíóúñ]+.*?\)')

    # Contexts
    contexts = []
    for para in paragraphs:
        for match in ctx_regex.finditer(para):
            contexts.append(match.group())

    # Entities

    # Delete initial article
    entities = [re.sub('el|la|El|La', '', ctx, 1).strip() for ctx in contexts]

    # Delete abbreviations
    entities = [re.sub('\(.*\)', '', ent).strip() for ent in entities]

    # Delete potential garbage
    entities = [re.split('[;,]', ent)[0] for ent in entities]

    # Abbreviations
    abbreviations = []
    context_clues = ['(a partir de)',
                     '(en lo sucesivo)',
                     '(de ahora en adelante)',
                     '(se entenderá por)',
                     '(se denominará como)']
    context_clues_regex = re.compile('|'.join(context_clues))
    for ctx in contexts:
        first_match = re.search('\(.*.*\)', ctx)
        if first_match:
            second_match = re.search('(\"|\“|\”|\').*(\“|\"|\”|\')', first_match.group())
            if second_match:
                abbreviations.append(second_match.group())
            else:
                trimmed = context_clues_regex.sub('', first_match.group())
                abbreviations.append(trimmed)
    abbreviations = [re.sub('\"|\“|\”|\'', '', ab).strip() for ab in abbreviations]

    # Serialize the info into CSV
    first_header = ['CONTEXTO', 'ENTIDAD', 'ABREVIATURAS']
    with open('entidades.csv', 'w') as f:
        writer = csv.writer(f)
        writer.writerow(first_header)
        for row in zip(contexts, entities, abbreviations):
            writer.writerow(row)

def sucesos(paragraphs):
    # Single dates
    single_date_regex = re.compile('de (%s) del?' % '|'.join(months))

    ctx_dates = []
    for para in paragraphs:
        match = single_date_regex.search(para)
        if match:
            ctx = ctx_sentence(para, single_date_regex)
            start = single_date_regex.search(ctx).start() - 3
            end = single_date_regex.search(ctx).end() + 5
            if start < 0:
                start = 0
            if end >= len(ctx):
                end = len(ctx)
            ctx_dates.append([ctx, date_parser(ctx[start : end])])

    # Where
    where_regex = re.compile('en ((el|la|los|las) )?(([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|(de(l| la| los)?))[ ,\.;])+')
    for cd in ctx_dates:
        match = where_regex.search(cd[0])
        if match:
            place = re.sub('en ((el|la|los|las) )?', '', match.group())
            cd.append(place)
        else:
            cd.append('')

    # In order to
    to_regex = re.compile('((((para )|(a fin de )|(con el objeto de ))que)|(con la finalidad de)|(para [a-záéíóúñ]+(ar|er|ir))).+[ \.;]')
    for cd in ctx_dates:
        match = to_regex.search(cd[0])
        if match:
            cd.append(match.group())
        else:
            cd.append('')

    # to whom
    whom_regex = re.compile('\\b(al?|(en favor de( la|l| los| las)?)) [a-záéíóú]* ?(([A-ZÁÉÍÓÚÑ][A-ZÁÉÍÓÚa-záéíóúñ]*|(de(l| los| la| las)?))[ ,\.;])*')
    for cd in ctx_dates:
        match = whom_regex.search(cd[0])
        if match:
            cd.append(match.group())
        else:
            cd.append('')

    # CSV serializer
    suc_header = ['CONTEXTO', 'FECHAS', 'LEMA', 'QUIÉN', 'QUÉ', 'DÓNDE', 'A QUIÉN', 'PARA QUÉ']
    with open('sucesos.csv', 'w') as f:
        writer = csv.writer(f)
        writer.writerow(suc_header)
        for data in ctx_dates:
            writer.writerow([data[0], data[1], '', '', '', data[2], data[4], data[3]])


def leyes(paragraphs):
    ctx_regex3 = re.compile('((el artículo)|(los artículos)).*[\.;]')
    # Contexts
    contexts3 = []
    for para in paragraphs:
        for match in ctx_regex3.finditer(para):
            splitted = match.group().split()
            ctx = ''
            for word in splitted:
                ctx += '{} '.format(word)
                if '.' in word or ';' in word:
                    if not re.match('[0-9]+o[\.;]', word):
                        contexts3.append(ctx.strip())
                        break
    # Laws
    def get_law(sentence):
        law_regex = re.compile('(de(l| la)) (([A-ZÁÉÍÓÚÑ][a-záéíóúñ]+|(de(l| la| los)))[ ,\.;])+')
        match = law_regex.search(sentence)
        if match:
            return re.sub('(de(l| la))', '', match.group(), 1).strip()
        else:
            return ''

    # Articles
    arab_num_regex = re.compile('[1-9][0-9]{,2}((o\.)|(-[A-Z]))?')
    roman_num_regex = re.compile('\\b[IVLX]+\\b')
    article_stack = []
    law_data = {}
    frac_mode = False
    for para in paragraphs:
        for word in para.split():
            match_arab = arab_num_regex.search(word)
            if match_arab:
                if frac_mode and article_stack:
                    article_stack.pop()
                frac_mode = False
                number = match_arab.group()
                try:
                    law_data[number]
                except KeyError:
                    reg = re.compile(number)
                    ctx_sent = ctx_sentence(para, reg)
                    law_data[number] = ([], ctx_sent,
                                        get_law(ctx_sent))
                article_stack.append(number)
            match_roman = roman_num_regex.search(word)
            if match_roman:
                frac_mode = True
                number = match_roman.group()
                if article_stack:
                    law_data[article_stack[-1]][0].append(number)

    # Data CSV serializer
    law_header = ['CONTEXTO', 'LEYES', 'ARTÍCULOS', 'FRACCIONES']
    with open('leyes.csv', 'w') as f:
        writer = csv.writer(f)
        writer.writerow(law_header)
        for art, (fracs, ctx, law) in law_data.items():
            if not fracs:
                writer.writerow([ctx, law, art, ''])
            for frac in fracs:
                writer.writerow([ctx, law, art, frac])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='script\'s argument parser')
    parser.add_argument('word_doc', help='document to analyze')
    args = parser.parse_args()

    # Read sample document
    document = Document(args.word_doc)

    paragraphs = [para.text for para in document.paragraphs]
    print('parsing entities...')
    entidades(paragraphs)
    print('parsing events...')
    sucesos(paragraphs)
    print('parsing laws...')
    leyes(paragraphs)
