from rest_framework import status
from rest_framework.decorators import api_view
from rest_framework.response import Response
# from jira import JIRA
# import os


# PASSWORD = os.getenv('JIRA_PASSWORD')
# USERNAME = os.getenv('JIRA_USERNAME')

# jira = JIRA()
# auth_jira = JIRA(auth=(USERNAME, PASSWORD))


@api_view(['GET'])
def automation_view(request):
    if request.method == 'GET':
        return Response(None, status=status.HTTP_200_OK)

