# -*- coding: utf-8 -*-


'''
##############
  WikiParser 
##############

* This module contains all the utility methods/functions that are used to process and parse the wikipedia 
  articles.

* This module also contains methods that process the information from wikipedia (using JSONpedia) and return 
  the appropriate JSON output to the mapper functions so that they could be easily processed to extract triples.

* Also contains methods that form the uri's from the string elements by making wikidata queries.

'''

import utilities
import time
import json
import sys
import subprocess

#set default encoding
reload(sys)
sys.setdefaultencoding('utf8')

last_sec_title = ""  # last section title parsed
header_title = ""  # last header (main section) title parsed
last_sec_lev = 0  # last section level parsed


def main_parser(language, resource):
    ''' **Main method**, obtains a **JSON** *representation* of a resource and stores the relevant data 
    in a dictionary.

    Asks JSONpedia for the JSON representing the resource and parses the result looking for lists in sections.
    Returns final dictionary containing all lists and their section names from given resource in given language.
    
    :param language: ``Language`` of Wikipedia page, needed by JSONpedia to identify the resource.
    :param resource: ``Resource name``, needed by JSONpedia.
    
    :return: a ``dictionary`` containing section names as keys and featured lists as values, without empty fields.
    '''

    global header_title  # used to concatenate sections and subsections titles
    lists = {}  # initialize dictionary
    result = jsonpedia_convert(language, resource)  # result obtained from JSONpedia in form of a list of sections
    
    if result == []:  #if the result is empty, try again looking for page redirects
        new_resource = find_page_redirects(resource, language)
        result = jsonpedia_convert(language, new_resource)
    
    for res in result:  # iterate on every section
        if '@type' in res and res['@type'] == 'section':
            parsed_sect = parse_section(res)
            lists.update(parsed_sect)
    cleanlists = utilities.clean_dictionary(language, lists)  #clean resulting dictionary and leave only meaningful keys
    
    return cleanlists


def parse_section(section):
    ''' Parses each section of the Wikipedia page searching for lists and calling ``parse_list()`` in turn.

    Returns a dictionary with section names as keys and their list contents as values.

    :param section: current section to parse in json format.
    :param title: a string used to concatenate names of nested sections.
    
    :return: a ``dictionary`` representing the section.
    '''
    
    global last_sec_lev
    global last_sec_title
    global header_title
    
    section_lists = {}  #initializing dictionary
    if ('content' in section and section['content'] != ""):  # parse only if there is available content
        # checks current level to know whether to concatenate the title or not
        if section['level'] == 0:  #this is a 'header title'
            title = section['title']
            header_title = title
        elif section['level'] > last_sec_lev:
            #must concatenate with the previous title and update 'header' for possible further depth
            title = last_sec_title + " - " + section['title']
            header_title = last_sec_title
        else:
            #just concatenate its title with current 'header'
            title = header_title + " - " + section['title']
        
        last_sec_title = title
        last_sec_lev = section['level']
        content = section['content'].values()  # don't consider keys since they are non-relevant (e.g. @an0, @an1,..)
        sect_list = []  # will contain the list extracted from current section
        """Extract section content - values inside dictionary inside 'content' key """
        
        for val in content:
            if ('@type' in val):
                if (val['@type'] == 'list'):  # look for lists inside current section
                    level = 1  # level is used to keep trace of list inception
                    nest_list = []  # will contain a nested list if there is one
                    for cont in val['content']:  # pass list elements to be parsed
                        if ('level' in cont and cont['level'] > level):  # check if current list element is nested
                            nest_cont = parse_list(cont)  #call parse_list on nested list and store it in nest_cont
                            nest_list.append(nest_cont)
                            sect_list.append(nest_list)
                            nest_list = []
                        else:
                            sect_list.append(parse_list(cont))
                    '''adds a new field in the dictionary representing list in the given section'''
                    section_lists[title] = sect_list
    return section_lists


def parse_list(list_elem):
    '''Parses a list element extracting relevant info and to be put in a string.

    It also marks `references (links)` with double curly brackets ``{{...}}`` in order to be recognizable 
    for mapping.
    
    :param list_elem: current list item in json format.

    :return: a string containing useful info from list element.
    '''
    list_content = ""  # initializing output
    if ('content' in list_elem and list_elem['content'] != None):
        for cont in list_elem['content']:
            if ('@type' in cont and cont['@type'] != 'list_element'):
                cont_type = cont['@type']
                if (cont_type == 'template' or cont_type == 'link'):  #Take only content field
                    tl_cont = cont['content']
                    if type(tl_cont) == list:
                        for tl_val in tl_cont.values():  # look for significant info in templates or links
                            list_content += tl_val[0] + " "
                    elif type(tl_cont) == dict:
                        if '@an0' in tl_cont:  # recurring structure type with an anonymous field '@an0'
                            tl_val = tl_cont['@an0']  # template content lies inside first anonymus value
                            if type(tl_val) == list:
                                for tlv in tl_val:
                                    if type(tlv) == dict:
                                        if 'label' in tlv:
                                            list_content += tlv['label']  # for references
                                    else:
                                        list_content += tlv + " "  # for actual values
                elif (cont_type == 'reference'):
                    list_content += " {{" + cont['label'] + "}} "  #this format helps me to discriminate the references
            elif ('label' in cont):  # if there is a label key, take only its value
                cont = cont['label']
                list_content = list_content + " " + cont + " "  # necessary to avoid lack of spaces between words
            elif ('attributes' not in cont):  # Take everything else but ignore bottom page references
                list_content += cont
    return list_content



'''

######################
### IMPORTANT NOTE ###
######################

* The jsonpedia_convert() and find_page_redirects() functions below are the older versions which make the
  calls to the JSONpedia Live service in order to obtain the resource's JSON representations. Since it's a
  web-service, high traffic and consistent/frequent requests can overload the server and make the 
  list-extractor unusable. Hence these are not used anymore.

* The newer versions of these functions use the JSONpedia library instead of the web-service, which makes 
  the list-extractor more robust and stable and is not dependent on the JSONpedia Live Service's server anymore.

* To use the older live web-request version (why though :P), uncomment the following two functions, and comment 
 the existing newer functions, in order to prevent name clashes.

'''

#####################
### Older Version ###
#####################

### Uncomment the lines below to use the web-request version.

# def jsonpedia_convert(language, resource):
#     ''' Calls JSONpedia online service to get a JSON representation of the Wikipedia page divided in sections

#     :param language: language of the resource we want to parse (e.g. it, en, fr...)
#     :param resource:  name of the resource

#     :return: a JSON with significant info about the resource
#     '''
#     res = language + "%3A" + resource
#     # JSONpedia call to obtain sections  - in this way I get both section titles and their lists
#     jsonpediaURL_sect = "http://jsonpedia.org/annotate/resource/json/" + res + "?filter=@type:section&procs=Structure"
    
#     try:
#         sections = utilities.json_req(jsonpediaURL_sect)
    
#     except (IOError):
#         print('Network Error - please check your connection and try again')
#         raise
#     except (ValueError):
#         raise
    
#     else:
#         if 'success' in sections and sections['success'] == "false":
#             if sections['message'] == 'Invalid page metadata.':
#                 print("JSONpedia error: Invalid wiki page."),
#                 raise
#             elif 'Expected DocumentElement found' in sections['message']:
#                 print(("JSONpedia error: something went wrong (DocumentElement expected).")),
#                 raise
#             else:
#                 print("JSONpedia error! - the web service may be currently overloaded, retrying... "
#                       "Error: " + sections['message'])
#                 time.sleep(1)  # wait one second before retrying
#                 return jsonpedia_convert(language, resource)  #try again JSONpedia call
        
#         else:
#             result = sections['result']  #JSON index with actual content
#             return result

# def find_page_redirects(res, lang):
#     '''Calls JSONpedia to find out whether the resource name provided redirects to another Wikipedia page

#     Returns the actual page if found, thus preventing from losing pages due to non-existing names.

#     :param lang: Wikipedia language of the resource
#     :param res: initial resource name which may trigger a redirection

#     :return: the redirection page if found
#     '''
#     redirect = []
#     jsonpedia_req = "http://jsonpedia.org/annotate/resource/json/" + lang + ":" + res + "?&procs=Structure"
#     result = utilities.json_req(jsonpedia_req)
#     if 'wikitext-dom' in result:
#         dom = result['wikitext-dom'][0]
#         if 'structure' in dom:
#             new_res = dom['structure'][1]['label']
#             redirect = new_res.replace(" ", "_").encode('utf-8')
#     return redirect


#####################
### Newer Version ###
#####################

### Comment the lines below to use the web-request version.

def jsonpedia_convert(language, resource):
    ''' Uses the ``JSONpedia wrapper`` to use the JSONpedia library to get a JSON representation of the 
        Wikipedia page divided in sections.

    :param language: language of the resource we want to parse `(e.g. it, en, fr...)`.
    :param resource:  name of the resource.

    :return: a JSON with significant info about the resource.
    '''
    try:
        # spawn a new process that makes a call to the json wrapper, which creates the required
        # json for the given resource, then load the string into a dict using json.loads()
        proc = subprocess.Popen(['java','-jar','jsonpedia_wrapper.jar','-l', language, 
                            '-r', resource, '-p', 'Structure', '-f', 'section'], stdout=subprocess.PIPE)
        pipe_output = proc.stdout.read()  #redirect the input into python variable
        proc.kill()  #kill the spawned process
        sections = json.loads(pipe_output) #load the string as a python dict

    #handle different errors
    except (IOError):
        print('Network Error - please check your connection and try again')
        raise
    except (ValueError):
        raise
    except (OSError):
        print('Error spawning process!')
        raise
    
    else:
        #JSONpedia call was succesfull
        if 'success' in sections and sections['success'] == "false":
            if sections['message'] == 'Invalid page metadata.':
                print("JSONpedia error: Invalid wiki page."),
                raise
            elif 'Expected DocumentElement found' in sections['message']:
                print(("JSONpedia error: something went wrong (DocumentElement expected).")),
                raise
            else:
                print("JSONpedia error! - the web service may be currently overloaded, retrying... "
                      "Error: " + sections['message'])
                time.sleep(1)  # wait one second before retrying
                return jsonpedia_convert(language, resource)  #try again JSONpedia call
        
        else:
            result = sections['result']  #JSON index with actual content
            return result

    pass

def find_page_redirects(res, lang):
    '''Calls ``JSONpedia wrapper`` to find out whether the resource name provided redirects to 
    another Wikipedia page. Returns the actual page if found, thus preventing from losing pages 
    due to non-existing names.

    :param lang: Wikipedia language of the resource.
    :param res: initial resource name which may trigger a redirection.
    
    :return: the redirection page, if found.
    '''
    try:
        # spawn a new process that makes a call to the json wrapper, which creates the required
        # json for the given resource, then load the string into a dict using json.loads()
        proc = subprocess.Popen(['java','-jar','jsonpedia_wrapper.jar','-l', language, 
                            '-r', resource, '-p', 'Structure'], stdout=subprocess.PIPE)
        pipe_output = proc.stdout.read()   #redirect the input into python variable
        proc.kill()  #kill the spawned process
        result = json.load(pipe_output)  #load the string as a python dict
        
    #handle different exceptions
    except (IOError):
        print('Network Error - please check your connection and try again')
        raise
    except (ValueError):
        raise
    except (OSError):
        print('Error spawning process!')
        raise

    redirect = []
    #find  if any redirects are present, if yes, return the redirect.
    if 'wikitext-dom' in result:
        dom = result['wikitext-dom'][0]
        if 'structure' in dom:
            new_res = dom['structure'][1]['label']
            redirect = new_res.replace(" ", "_").encode('utf-8')
    return redirect