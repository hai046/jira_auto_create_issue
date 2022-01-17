# !/usr/bin/python
# -*- coding: UTF-8 -*-
import csv
import json
import sys

import requests
from config import TOKEN_HEADERS
from config import DOMAIN


class jira_issue:
    # issuetypes
    # 对应的名字，通过 /rest/api/2/issue/createmeta
    # 获取对应名字，因为英文或者其他的原因可能定义不一直，需要确认对应关系
    type_epic = 'Epic'
    type_task = '任务'
    type_sub_task = '子任务'

    def __init__(self, project='', version=''):
        self.__version = version
        self.__project = project
        self.__keys_map = {}
        self.__name_mapper = {}
        # 缓存已经创建的issue，防止重复创建
        self.__search_issue()
        # 找到name和displayName的对应关系，因为导入的时候是通过displayName创建的
        self.__search_user()
        self.token_headers = TOKEN_HEADERS
        self.token_headers = DOMAIN

    # rest api 接口地址 https://developer.atlassian.com/cloud/jira/platform/rest/v2/api-group-issues/#api-rest-api-2-issue-post

    def import_csv(self, file, skip_line=1):
        with open(file, 'r', newline='', encoding='utf-8') as f:
            count = 0
            reader = csv.reader(f)
            epic = ''
            task = ''
            for row in reader:
                count += 1
                if count <= skip_line:
                    continue
                epic = row[0].strip() if row[0] != '' else epic
                task = row[1].strip() if row[1] != '' else task
                sub_task = row[2].strip() if row[2] != '' else task  # 如果子任务没有些就是父任务
                cost_hour = row[3].strip()
                user = row[4].strip()
                priority = row[5].strip()

                if self.type_epic + epic not in self.__keys_map:
                    epic_key = self.create_epic(epic)
                    self.__keys_map[self.type_epic + epic] = epic_key
                else:
                    epic_key = self.__keys_map[self.type_epic + epic]

                if self.type_task + task not in self.__keys_map:
                    task_key = self.create_task(epic_key, task)
                    self.__keys_map[self.type_task + task] = task_key
                else:
                    task_key = self.__keys_map[self.type_task + task]
                if self.type_sub_task + sub_task not in self.__keys_map:
                    self.create_sub_task(task_key, sub_task, cost_hour, user, priority=priority)

        pass

    def create_epic(self, epic):
        '''
        创建epic
        :param epic:
        :return:
        '''
        url = '%s/rest/api/2/issue' % self.jira_domain
        response = requests.post(url, headers=self.token_headers, json={
            "fields": {
                "summary": '%s' % (epic),
                "project": {
                    "key": self.__project
                },
                "issuetype": {
                    "name": self.type_epic
                },
                "versions": [
                    {'name': self.__version}
                ],
                "description": epic,
                "customfield_10103": epic,
            }
        })
        print(response.text)
        payload = json.loads(response.text)
        return payload['key']
        pass

    def delete_issue(self, id):
        print('del id', id)
        url = '%s/rest/api/2/issue/%s-%s?deleteSubtasks=true' % (self.jira_domain, self.__project, id)
        response = requests.delete(url, headers=self.token_headers)
        print(response.text)
        pass

    def create_task(self, epic_key, task):
        url = '%s/rest/api/2/issue' % self.jira_domain
        response = requests.post(url, headers=self.token_headers, json={
            "fields": {
                "summary": '%s' % (task),
                "project": {
                    "key": self.__project
                },
                "issuetype": {
                    "name": self.type_task
                },
                "versions": [
                    {'name': self.__version}
                ],
                # 需求列表【长篇故事中的事务】
                'customfield_10101': epic_key,
                "description": task,
            }})
        print(response.text)
        payload = json.loads(response.text)
        return payload['key']
        pass

    def create_sub_task(self, task_key, sub_task, cost_hour, user, priority='Medium'):
        if cost_hour == '':
            cost_hour = '0'
        url = '%s/rest/api/2/issue' % self.jira_domain
        if user in self.__name_mapper:
            # 映射中文名字到英文名
            user = self.__name_mapper[user]
        response = requests.post(url, headers=self.token_headers, json={
            "fields": {
                "summary": '%s' % (sub_task),
                "project": {
                    "key": self.__project
                },
                "parent": {
                    "key": task_key
                },
                "issuetype": {
                    "name": self.type_sub_task
                },
                "assignee": {
                    "name": user
                },
                "priority": {
                    "name": priority
                },
                "versions": [
                    {'name': self.__version}
                ],
                "description": sub_task,
                "timetracking": {
                    "originalEstimate": "0m",
                    "remainingEstimate": "0m",
                    "originalEstimateSeconds": 0,
                    "remainingEstimateSeconds": 0
                },

                "customfield_10400": int(cost_hour) * 60,
            }
        })
        print(response.text)
        payload = json.loads(response.text)
        return payload['key']
        pass

    def test(self):
        url = '%s/rest/api/2/issue/createmeta' % (self.jira_domain)
        response = requests.get(url, headers=self.token_headers, json={})
        print(response.text)
        exit()
        pass

    def __search_issue(self):
        print('搜索历史数据，防止重复')
        url = '%s/rest/api/2/search' % (self.jira_domain)
        response = requests.post(url, headers=self.token_headers, json={
            "expand": [
                "names",
                "schema",
                "operations"
            ],
            "jql": "project = %s and affectedVersion = %s " % (self.__project, self.__version),
            # "jql": "",
            "maxResults": 1500,
            # "fieldsByKeys": False,
            "fields": [
                "summary",
                "issuetype",
                # "assignee"
            ],
            # "startAt": 0
        })
        payload = json.loads(response.text)
        if 'issues' in payload:
            for issue in payload['issues']:
                fields = issue['fields']
                name = fields['issuetype']['name']
                summary = fields['summary']
                self.__keys_map[name + summary] = issue['key']

        print(self.__keys_map)
        pass

    def __search_user(self):
        url = '%s/rest/api/2/user/assignable/search' % (self.jira_domain)
        response = requests.get(url,
                                params={"project": self.__project},
                                headers=self.token_headers)
        # displayName和名字映射关系   这里是自己匹配导入文档名字和jira英文名字对应关系
        print(response.text)
        payload = json.loads(response.text)
        for user in payload:
            name = user['name']
            displayName = str(user['displayName']).split('-')[0]
            self.__name_mapper[displayName] = name
        pass


if __name__ == '__main__':

    if len(sys.argv) != 4:
        print("必须有3个参数， jira.py [project] [version] [path]")
        exit()
    project = sys.argv[1]
    version = sys.argv[2]
    path = sys.argv[3]
    t = jira_issue(project=project, version=version)
    # for i in range(431, 436):
    #     t.delete_issue(i)
    # t.get_issues('ZSYY-842')
    # t.import_csv('/Users/hai046/Downloads/2.6.0 迭代计划 - 2.6.0.csv')
    t.import_csv(path)
