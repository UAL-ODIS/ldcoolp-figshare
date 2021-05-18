from typing import Tuple
from requests.exceptions import HTTPError

import pandas as pd
import numpy as np

from logging import Logger
from redata.commons.logger import log_stdout
from redata.commons.issue_request import redata_request


class FigshareInstituteAdmin:
    """
    A Python interface for administration and data curation
    with institutional Figshare instances

    :param token: Figshare OAuth2 authentication token
    :param stage: Flag to either use Figshare stage or prod API
    :param admin_filter: List of filters to remove admin accounts from user list
    :param log: Logger object for stdout and file logging. Default: stdout

    :ivar token: Figshare OAuth2 authentication token
    :ivar stage: Flag to either use Figshare stage or prod API
    :ivar baseurl: Base URL of Figshare API
    :ivar baseurl_institute: Base URL of Figshare API for institutions
    :ivar token: Figshare OAuth2 authentication token
    :ivar headers: HTTP header information
    :ivar admin_filter: List of filters to remove admin accounts from user list
    :ivar ignore_admin: Flags whether to remove admin accounts from user list
    """

    def __init__(self, token: str, stage: bool = False,
                 admin_filter: list = None,
                 log: Logger = log_stdout()):

        self.token = token
        self.stage = stage

        if not self.stage:
            self.baseurl = "https://api.figshare.com/v2/account/"
        else:
            self.baseurl = "https://api.figsh.com/v2/account/"

        self.baseurl_institute = self.baseurl + "institution/"

        self.headers = {'Content-Type': 'application/json'}
        if self.token:
            self.headers['Authorization'] = f'token {self.token}'

        self.admin_filter = admin_filter
        if admin_filter is not None:
            self.ignore_admin = True
        else:
            self.ignore_admin = False
        self.log = log

    def endpoint(self, link: str, institute: bool = True) -> str:
        """Concatenate the endpoint to the baseurl"""
        if institute:
            return self.baseurl_institute + link
        else:
            return self.baseurl + link

    def get_articles(self) -> pd.DataFrame:
        """
        Retrieve information about articles within institutional instance
        See: https://docs.figshare.com/#private_institution_articles
        """

        url = self.endpoint("articles")

        # Figshare API is limited to a maximum of 1000 per page
        params = {'page': 1, 'page_size': 1000}
        articles = redata_request('GET', url, self.headers, params=params)

        articles_df = pd.DataFrame(articles)
        return articles_df

    def get_user_articles(self, account_id: int) -> pd.DataFrame:
        """
        Impersonate a user to retrieve articles associated with the user
        See: https://docs.figshare.com/#private_articles_list
        """

        url = self.endpoint("articles", institute=False)

        # Figshare API is limited to a maximum of 1000 per page
        params = {'page': 1, 'page_size': 1000, 'impersonate': account_id}
        user_articles = redata_request('GET', url, self.headers, params=params)

        user_articles_df = pd.DataFrame(user_articles)
        return user_articles_df

    def get_user_projects(self, account_id: int) -> pd.DataFrame:
        """
        Impersonate a user to retrieve projects associated with the user
        See: https://docs.figshare.com/#private_projects_list
        """

        url = self.endpoint("projects", institute=False)

        # Figshare API is limited to a maximum of 1000 per page
        params = {'page': 1, 'page_size': 1000, 'impersonate': account_id}
        user_projects = redata_request('GET', url, self.headers, params=params)

        user_projects_df = pd.DataFrame(user_projects)
        return user_projects_df

    def get_user_collections(self, account_id: int) -> pd.DataFrame:
        """
        Impersonate a user to retrieve collections associated with the user
        See: https://docs.figshare.com/#private_collections_list
        """

        url = self.endpoint("collections", institute=False)

        # Figshare API is limited to a maximum of 1000 per page
        params = {'page': 1, 'page_size': 1000, 'impersonate': account_id}
        user_collections = redata_request('GET', url, self.headers, params=params)

        user_collections_df = pd.DataFrame(user_collections)
        return user_collections_df

    def get_groups(self) -> pd.DataFrame:
        """
        Retrieve information about groups within institutional instance
        See: https://docs.figshare.com/#private_institution_groups_list
        """

        url = self.endpoint("groups")
        groups = redata_request('GET', url, self.headers)

        groups_df = pd.DataFrame(groups)
        return groups_df

    def get_account_list(self) -> pd.DataFrame:
        """
        Return pandas DataFrame of user accounts
        See: https://docs.figshare.com/#private_institution_accounts_list
        """

        url = self.endpoint("accounts")

        # Figshare API is limited to a maximum of 1000 per page
        params = {'page': 1, 'page_size': 1000}
        accounts = redata_request('GET', url, self.headers, params=params)

        accounts_df = pd.DataFrame(accounts)
        accounts_df = accounts_df.drop(columns='institution_id')

        if self.ignore_admin:
            self.log.info("Excluding administrative and test accounts")

            drop_index = []
            for ia in self.admin_filter:
                drop_index += list(accounts_df[accounts_df['email'].str.contains(ia)].index)

            accounts_df = accounts_df.drop(drop_index).reset_index(drop=True)
        return accounts_df

    def get_account_group_roles(self, account_id: int) -> dict:
        """
        Retrieve group roles for a given account
        See: https://docs.figshare.com/#private_institution_account_group_roles
        """

        url = self.endpoint(f"roles/{account_id}")

        roles = redata_request('GET', url, self.headers)
        return roles

    def get_account_details(self, flag: bool = True) -> pd.DataFrame:
        """
        Retrieve account details. This includes number of articles, projects,
        collections, group association, and administrative and reviewer flags
        """

        # Retrieve accounts
        accounts_df = self.get_account_list()

        n_accounts = accounts_df.shape[0]

        # Retrieve groups
        groups_df = self.get_groups()

        num_articles = np.zeros(n_accounts, dtype=np.int)
        num_projects = np.zeros(n_accounts, dtype=np.int)
        num_collections = np.zeros(n_accounts, dtype=np.int)

        if flag:
            admin_flag = [''] * n_accounts
            reviewer_flag = [''] * n_accounts
        group_assoc = ['N/A'] * n_accounts

        # Determine group roles for each account
        for n, account_id in zip(range(n_accounts), accounts_df['id']):
            roles = self.get_account_group_roles(account_id)

            try:
                articles_df = self.get_user_articles(account_id)
                num_articles[n] = articles_df.shape[0]
            except HTTPError:
                self.log.warning(f"Unable to retrieve articles for : {account_id}")

            try:
                projects_df = self.get_user_projects(account_id)
                num_projects[n] = projects_df.shape[0]
            except HTTPError:
                self.log.warning(f"Unable to retrieve projects for : {account_id}")

            try:
                collections_df = self.get_user_collections(account_id)
                num_collections[n] = collections_df.shape[0]
            except HTTPError:
                self.log.warning(f"Unable to retrieve collections for : {account_id}")

            for key in roles.keys():
                for t_dict in roles[key]:
                    if t_dict['id'] == 11:
                        group_assoc[n] = key
                    if flag:
                        if t_dict['id'] == 2:
                            admin_flag[n] = 'X'
                        if t_dict['id'] == 49:
                            reviewer_flag[n] = 'X'

        accounts_df['Articles'] = num_articles
        accounts_df['Projects'] = num_projects
        accounts_df['Collections'] = num_collections

        if flag:
            accounts_df['Admin'] = admin_flag
            accounts_df['Reviewer'] = reviewer_flag

        for group_id, group_name in zip(groups_df['id'], groups_df['name']):
            self.log.info(f"{group_id} - {group_name}")
            group_assoc = [sub.replace(str(group_id), group_name) for
                           sub in group_assoc]

        accounts_df['Group'] = group_assoc
        return accounts_df

    def get_curation_list(self, article_id: int = None) -> pd.DataFrame:
        """
        Retrieve list of curation
        See: https://docs.figshare.com/#account_institution_curations
        """

        url = self.endpoint("reviews")

        params = {'offset': 0, 'limit': 1000}
        if article_id is not None:
            params['article_id'] = article_id

        curation_list = redata_request('GET', url, self.headers,
                                       params=params)

        curation_df = pd.DataFrame(curation_list)
        return curation_df

    def get_curation_details(self, curation_id: int) -> dict:
        """
        Retrieve details about a specified curation item
        https://docs.figshare.com/#account_institution_curation
        """

        url = self.endpoint(f"review/{curation_id}")

        curation_details = redata_request('GET', url, self.headers)
        return curation_details

    def get_curation_comments(self, curation_id: int) -> dict:
        """
        Retrieve comments about specified curation item
        See: https://docs.figshare.com/#account_institution_curation_comments
        """

        url = self.endpoint(f"review/{curation_id}/comments")

        curation_comments = redata_request('GET', url, self.headers)
        return curation_comments

    def doi_check(self, article_id: int) -> Tuple[bool, str]:
        """
        Check if DOI is present/reserved
        Uses: https://docs.figshare.com/#private_article_details
        """
        url = self.endpoint(f"articles/{article_id}", institute=False)

        article_details = redata_request('GET', url, self.headers)

        check = False
        if article_details['doi']:
            check = True

        return check, article_details['doi']

    def reserve_doi(self, article_id: int) -> str:
        """
        Reserve DOI if one has not been reserved
        See: https://docs.figshare.com/#private_article_reserve_doi
        """

        url = self.endpoint(f"articles/{article_id}/reserve_doi", institute=False)

        # Check if DOI has been reserved
        doi_check, doi_string = self.doi_check(article_id)

        if doi_check:
            self.log.info("DOI already reserved! Skipping... ")
            return doi_string
        else:
            self.log.info("PROMPT: DOI reservation has not occurred! Do you wish to reserve?")
            src_input = input("PROMPT: Type 'Yes'/'yes'. Anything else will skip : ")
            self.log.info(f"RESPONSE: {src_input}")
            if src_input.lower() == 'yes':
                self.log.info("Reserving DOI ... ")
                response = redata_request('POST', url, self.headers)
                self.log.info(f"DOI minted : {response['doi']}")
                return response['doi']
            else:
                self.log.warning("Skipping... ")
                return doi_string
