import requests
from bs4 import BeautifulSoup
import csv
import pandas as pd
import argparse

class ProfFinder:
    '''
    This class provides methods for finding professors from Stanford Engineering with research
    interests matching a given query.
    '''
    def __init__(self):
        self.index_link = 'https://engineering.stanford.edu'
        self.grid_link = self.index_link + '/people/faculty/grid'
    
    def get(self, filename):
        '''
        Downloads data for each Professor from the Stanford Engineering website
        and saves to path given by filename, as a csv with columns ['Name', 'Webpage', 'Research']
        '''
        source = requests.get(self.grid_link).text
        soup = BeautifulSoup(source, 'lxml')
        grid = soup.find('div', class_='view-content')
        profs = grid.find_all('div', class_='views-row')
        with open(filename, 'w') as f:
            csvwriter = csv.writer(f, delimiter='\t')
            csvwriter.writerow(['Name', 'Webpage', 'Research'])
            for prof in profs:
                try:
                    prof_page_link = self.index_link + prof.find('h3').a['href']
                    prof_source = requests.get(prof_page_link).text
                    prof_soup = BeautifulSoup(prof_source, 'lxml')
                    prof_about = prof_soup.find('div', class_='group-s-about')
                    prof_description = prof_about.find('div', class_='field-item').text
                    csvwriter.writerow([prof.h3.a.text, prof_page_link, prof_description])
                except:
                    pass

    def find(self, query, filename):
        '''
        This method expects data stored in path given by filename in the same format as produced by the get()
        method of this class. It returns a pandas dataframe consisting of professors' names whose research
        interests match that of the query and along with links to their web pages.
        '''
        df = pd.read_csv(filename, sep='\t')
        df_result = df[df['Research'].str.contains(query)]
        return df_result[['Name', 'Webpage']]

if __name__ == "__main__":

    ap = argparse.ArgumentParser()
    ap.add_argument('-f', '--filename', required=True, help='Filename')
    ap.add_argument('-q', '--query', required=True, help='Query')
    args = vars(ap.parse_args())

    prof_finder = ProfFinder()

    ###### Uncomment the below line if scraped data is not available
    #prof_finder.get(args['filename'])
    
    df = prof_finder.find(args['query'],args['filename'])
    print(df)



# index_link = 'https://engineering.stanford.edu'

# grid_link = index_link + '/people/faculty/grid'

# source = requests.get(grid_link).text

# soup = BeautifulSoup(source, 'lxml')

# grid = soup.find('div', class_='view-content')

# profs = grid.find_all('div', class_='views-row')

# with open('allprofs.csv', 'w') as f:
#     csvwriter = csv.writer(f, delimiter='\t')
#     csvwriter.writerow(['Name', 'Webpage', 'Work'])
#     for prof in profs:
#         try:
#             prof_page_link = index_link + prof.find('h3').a['href']
#             prof_source = requests.get(prof_page_link).text
#             prof_soup = BeautifulSoup(prof_source, 'lxml')
#             prof_about = prof_soup.find('div', class_='group-s-about')
#             prof_description = prof_about.find('div', class_='field-item').text
#             csvwriter.writerow([prof.h3.a.text, prof_page_link, prof_description])
#         except:
#             pass
    


