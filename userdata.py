from uuid import uuid4
import pandas as pd
from neo4jdata import Graph
import requests
from psycopg2 import pool
import os
import bcrypt
from dotenv import load_dotenv

class userdata:
    def __init__(self) -> None:
        self.graph = Graph()
        self.db_config =  {
            "minconn":1,
            "maxconn":5,
            "host": os.environ.get("PG_HOST"),
            "port": os.environ.get("PG_PORT"),
            "dbname": 'quilr',
            "user": os.environ.get("PG_USER"),
            "password": os.environ.get("PG_PASSWORD")
        }
        self.conn = pool.SimpleConnectionPool(**self.db_config)
        self.query = '''
MERGE (TENANT_0:TENANT {id: $TENANT_0_id, subscriber: $TENANT_0_subscriber, tenant: $TENANT_0_tenant})
ON CREATE
         SET
                 TENANT_0.creationTime = $TENANT_0_creationTime,
                 TENANT_0.subscriber = $TENANT_0_subscriber,
                 TENANT_0.tenant = $TENANT_0_tenant,
                 TENANT_0.internalId = randomUUID(),
                 TENANT_0.new = true,
                 TENANT_0.timestamp = timestamp()
ON MATCH
         SET
                 TENANT_0.subscriber = $TENANT_0_subscriber,
                 TENANT_0.tenant = $TENANT_0_tenant,
                 TENANT_0.new = false,
                 TENANT_0.timestamp = timestamp()
WITH TENANT_0

MERGE (INSTANCE_0:INSTANCE {id: $INSTANCE_0_id, subscriber: $INSTANCE_0_subscriber, tenant: $INSTANCE_0_tenant})
ON CREATE
         SET
                 INSTANCE_0.creationTime = $INSTANCE_0_creationTime,
                 INSTANCE_0.subscriber = $INSTANCE_0_subscriber,
                 INSTANCE_0.tenant = $INSTANCE_0_tenant,
                 INSTANCE_0.internalId = randomUUID(),
                 INSTANCE_0.new = true,
                 INSTANCE_0.timestamp = timestamp()
ON MATCH
         SET
                 INSTANCE_0.subscriber = $INSTANCE_0_subscriber,
                 INSTANCE_0.tenant = $INSTANCE_0_tenant,
                 INSTANCE_0.new = false,
                 INSTANCE_0.timestamp = timestamp()
WITH TENANT_0, INSTANCE_0

MERGE (IDP_APPLICATION_0:APPLICATION {id_: $IDP_APPLICATION_0_id_})
ON CREATE
         SET
                 IDP_APPLICATION_0.domain = $IDP_APPLICATION_0_domain,
                 IDP_APPLICATION_0.newApp = $IDP_APPLICATION_0_newApp,
                 IDP_APPLICATION_0.globalSyncAllowed = $IDP_APPLICATION_0_globalSyncAllowed,
                 IDP_APPLICATION_0.internalId = randomUUID(),
                 IDP_APPLICATION_0.new = true,
                 IDP_APPLICATION_0.timestamp = timestamp()
ON MATCH
         SET
                 IDP_APPLICATION_0.new = false,
                 IDP_APPLICATION_0.timestamp = timestamp()
WITH TENANT_0, INSTANCE_0, IDP_APPLICATION_0

MERGE (ACCOUNT_MAIN_0:ACCOUNT {id: $ACCOUNT_MAIN_0_id, subscriber: $ACCOUNT_MAIN_0_subscriber, tenant: $ACCOUNT_MAIN_0_tenant})
ON CREATE
         SET
                 ACCOUNT_MAIN_0.creationTime = $ACCOUNT_MAIN_0_creationTime,
                 ACCOUNT_MAIN_0.email = $ACCOUNT_MAIN_0_email,
                 ACCOUNT_MAIN_0.appName = $ACCOUNT_MAIN_0_appName,
                 ACCOUNT_MAIN_0.subscriber = $ACCOUNT_MAIN_0_subscriber,
                 ACCOUNT_MAIN_0.tenant = $ACCOUNT_MAIN_0_tenant,
                 ACCOUNT_MAIN_0.internalId = randomUUID(),
                 ACCOUNT_MAIN_0.new = true,
                 ACCOUNT_MAIN_0.timestamp = timestamp()
ON MATCH
         SET
                 ACCOUNT_MAIN_0.email = $ACCOUNT_MAIN_0_email,
                 ACCOUNT_MAIN_0.appName = $ACCOUNT_MAIN_0_appName,
                 ACCOUNT_MAIN_0.subscriber = $ACCOUNT_MAIN_0_subscriber,
                 ACCOUNT_MAIN_0.tenant = $ACCOUNT_MAIN_0_tenant,
                 ACCOUNT_MAIN_0.new = false,
                 ACCOUNT_MAIN_0.timestamp = timestamp()
WITH TENANT_0, INSTANCE_0, IDP_APPLICATION_0, ACCOUNT_MAIN_0

MERGE (USER_0:USER {id: $USER_0_id, subscriber: $USER_0_subscriber, tenant: $USER_0_tenant})
ON CREATE
         SET
                 USER_0.extensionDeploymentStatus = $USER_0_extensionDeploymentStatus,
                 USER_0.copilotStatus = $USER_0_copilotStatus,
                 USER_0.displayName = $USER_0_displayName,
                 USER_0.givenName = $USER_0_givenName,
                 USER_0.middleName = $USER_0_middleName,
                 USER_0.orgCode = $USER_0_orgCode,
                 USER_0.empType = $USER_0_empType,
                 USER_0.workFrom = $USER_0_workFrom,
                 USER_0.jobTitle = $USER_0_jobTitle,
                 USER_0.mail = $USER_0_mail,
                 USER_0.mobilePhone = $USER_0_mobilePhone,
                 USER_0.preferredLanguage = $USER_0_preferredLanguage,
                 USER_0.signInActivity = $USER_0_signInActivity,
                 USER_0.surname = $USER_0_surname,
                 USER_0.userPrincipalName = $USER_0_userPrincipalName,
                 USER_0.userType = $USER_0_userType,
                 USER_0.securityIdentifier = $USER_0_securityIdentifier,
                 USER_0.businessPhones = $USER_0_businessPhones,
                 USER_0.street = $USER_0_street,
                 USER_0.country = $USER_0_country,
                 USER_0.zipCode = $USER_0_zipCode,
                 USER_0.city = $USER_0_city,
                 USER_0.employeeHireDate = $USER_0_employeeHireDate,
                 USER_0.userCreationTime = $USER_0_userCreationTime,
                 USER_0.state = $USER_0_state,
                 USER_0.employeeType = $USER_0_employeeType,
                 USER_0.companyName = $USER_0_companyName,
                 USER_0.accountEnabled = $USER_0_accountEnabled,
                 USER_0.terminationDate = $USER_0_terminationDate,
                 USER_0.profilePicUrl = $USER_0_profilePicUrl,
                 USER_0.suspensionReason = $USER_0_suspensionReason,
                 USER_0.userIsadmin = $USER_0_userIsadmin,
                 USER_0.userDelegationadmin = $USER_0_userDelegationadmin,
                 USER_0.userLastLoginTime = $USER_0_userLastLoginTime,
                 USER_0.userAgreedterms = $USER_0_userAgreedterms,
                 USER_0.userSuspended = $USER_0_userSuspended,
                 USER_0.userArchived = $USER_0_userArchived,
                 USER_0.usermobiletype = $USER_0_usermobiletype,
                 USER_0.userCustomerID = $USER_0_userCustomerID,
                 USER_0.userIsMailboxSetup = $USER_0_userIsMailboxSetup,
                 USER_0.userIs2svEnrolled = $USER_0_userIs2svEnrolled,
                 USER_0.userIsforcedIn2sv = $USER_0_userIsforcedIn2sv,
                 USER_0.userIncludeInGlobalAddressList = $USER_0_userIncludeInGlobalAddressList,
                 USER_0.userChangedPasswordAtNextLogin = $USER_0_userChangedPasswordAtNextLogin,
                 USER_0.userOrgUnitPath = $USER_0_userOrgUnitPath,
                 USER_0.userIpWhitelisted = $USER_0_userIpWhitelisted,
                 USER_0.subscriber = $USER_0_subscriber,
                 USER_0.tenant = $USER_0_tenant,
                 USER_0.internalId = randomUUID(),
                 USER_0.new = true,
                 USER_0.timestamp = timestamp()
ON MATCH
         SET
                 USER_0.displayName = $USER_0_displayName,
                 USER_0.givenName = $USER_0_givenName,
                 USER_0.middleName = $USER_0_middleName,
                 USER_0.orgCode = $USER_0_orgCode,
                 USER_0.empType = $USER_0_empType,
                 USER_0.workFrom = $USER_0_workFrom,
                 USER_0.jobTitle = $USER_0_jobTitle,
                 USER_0.mail = $USER_0_mail,
                 USER_0.mobilePhone = $USER_0_mobilePhone,
                 USER_0.preferredLanguage = $USER_0_preferredLanguage,
                 USER_0.signInActivity = $USER_0_signInActivity,
                 USER_0.surname = $USER_0_surname,
                 USER_0.userPrincipalName = $USER_0_userPrincipalName,
                 USER_0.userType = $USER_0_userType,
                 USER_0.securityIdentifier = $USER_0_securityIdentifier,
                 USER_0.businessPhones = $USER_0_businessPhones,
                 USER_0.street = $USER_0_street,
                 USER_0.country = $USER_0_country,
                 USER_0.zipCode = $USER_0_zipCode,
                 USER_0.city = $USER_0_city,
                 USER_0.employeeHireDate = $USER_0_employeeHireDate,
                 USER_0.userCreationTime = $USER_0_userCreationTime,
                 USER_0.state = $USER_0_state,
                 USER_0.employeeType = $USER_0_employeeType,
                 USER_0.companyName = $USER_0_companyName,
                 USER_0.accountEnabled = $USER_0_accountEnabled,
                 USER_0.terminationDate = $USER_0_terminationDate,
                 USER_0.profilePicUrl = $USER_0_profilePicUrl,
                 USER_0.suspensionReason = $USER_0_suspensionReason,
                 USER_0.userIsadmin = $USER_0_userIsadmin,
                 USER_0.userDelegationadmin = $USER_0_userDelegationadmin,
                 USER_0.userLastLoginTime = $USER_0_userLastLoginTime,
                 USER_0.userAgreedterms = $USER_0_userAgreedterms,
                 USER_0.userSuspended = $USER_0_userSuspended,
                 USER_0.userArchived = $USER_0_userArchived,
                 USER_0.usermobiletype = $USER_0_usermobiletype,
                 USER_0.userCustomerID = $USER_0_userCustomerID,
                 USER_0.userIsMailboxSetup = $USER_0_userIsMailboxSetup,
                 USER_0.userIs2svEnrolled = $USER_0_userIs2svEnrolled,
                 USER_0.userIsforcedIn2sv = $USER_0_userIsforcedIn2sv,
                 USER_0.userIncludeInGlobalAddressList = $USER_0_userIncludeInGlobalAddressList,
                 USER_0.userChangedPasswordAtNextLogin = $USER_0_userChangedPasswordAtNextLogin,
                 USER_0.userOrgUnitPath = $USER_0_userOrgUnitPath,
                 USER_0.userIpWhitelisted = $USER_0_userIpWhitelisted,
                 USER_0.subscriber = $USER_0_subscriber,
                 USER_0.tenant = $USER_0_tenant,
                 USER_0.new = false,
                 USER_0.timestamp = timestamp()
WITH TENANT_0, INSTANCE_0, IDP_APPLICATION_0, ACCOUNT_MAIN_0, USER_0

MERGE (EMAILPRIMARY_0:EMAIL {id: $EMAILPRIMARY_0_id, subscriber: $EMAILPRIMARY_0_subscriber, tenant: $EMAILPRIMARY_0_tenant})
ON CREATE
         SET
                 EMAILPRIMARY_0.subscriber = $EMAILPRIMARY_0_subscriber,
                 EMAILPRIMARY_0.tenant = $EMAILPRIMARY_0_tenant,
                 EMAILPRIMARY_0:PRIMARY,
                 EMAILPRIMARY_0.internalId = randomUUID(),
                 EMAILPRIMARY_0.new = true,
                 EMAILPRIMARY_0.timestamp = timestamp()
ON MATCH
         SET
                 EMAILPRIMARY_0.subscriber = $EMAILPRIMARY_0_subscriber,
                 EMAILPRIMARY_0.tenant = $EMAILPRIMARY_0_tenant,
                 EMAILPRIMARY_0:PRIMARY,
                 EMAILPRIMARY_0.new = false,
                 EMAILPRIMARY_0.timestamp = timestamp()
WITH TENANT_0, INSTANCE_0, IDP_APPLICATION_0, ACCOUNT_MAIN_0, USER_0, EMAILPRIMARY_0

MERGE (DEPARTMENT_0:DEPARTMENT {id: $DEPARTMENT_0_id, subscriber: $DEPARTMENT_0_subscriber, tenant: $DEPARTMENT_0_tenant})
ON CREATE
         SET
                 DEPARTMENT_0.name = $DEPARTMENT_0_name,
                 DEPARTMENT_0.subscriber = $DEPARTMENT_0_subscriber,
                 DEPARTMENT_0.tenant = $DEPARTMENT_0_tenant,
                 DEPARTMENT_0.internalId = randomUUID(),
                 DEPARTMENT_0.new = true,
                 DEPARTMENT_0.timestamp = timestamp()
ON MATCH
         SET
                 DEPARTMENT_0.name = $DEPARTMENT_0_name,
                 DEPARTMENT_0.subscriber = $DEPARTMENT_0_subscriber,
                 DEPARTMENT_0.tenant = $DEPARTMENT_0_tenant,
                 DEPARTMENT_0.new = false,
                 DEPARTMENT_0.timestamp = timestamp()
WITH TENANT_0, INSTANCE_0, IDP_APPLICATION_0, ACCOUNT_MAIN_0, USER_0, EMAILPRIMARY_0, DEPARTMENT_0

WITH TENANT_0, INSTANCE_0, IDP_APPLICATION_0, ACCOUNT_MAIN_0, USER_0, EMAILPRIMARY_0, DEPARTMENT_0

WITH TENANT_0, INSTANCE_0, IDP_APPLICATION_0, ACCOUNT_MAIN_0, USER_0, EMAILPRIMARY_0, DEPARTMENT_0

MERGE (TENANT_0)-[tenant_0_instance_0_has_instance:HAS_INSTANCE]->(INSTANCE_0)
ON CREATE
         SET
                 tenant_0_instance_0_has_instance.internalId = randomUUID(),
                 tenant_0_instance_0_has_instance.new = true,
                 tenant_0_instance_0_has_instance.timestamp = timestamp()
ON MATCH
         SET
                 tenant_0_instance_0_has_instance.new = false,
                 tenant_0_instance_0_has_instance.timestamp = timestamp()

MERGE (INSTANCE_0)-[instance_0_user_0_has_user:HAS_USER]->(USER_0)
ON CREATE
         SET
                 instance_0_user_0_has_user.internalId = randomUUID(),
                 instance_0_user_0_has_user.new = true,
                 instance_0_user_0_has_user.timestamp = timestamp()
ON MATCH
         SET
                 instance_0_user_0_has_user.new = false,
                 instance_0_user_0_has_user.timestamp = timestamp()

MERGE (ACCOUNT_MAIN_0)-[account_main_0_idp_application_0_using_app:USING_APP]->(IDP_APPLICATION_0)
ON CREATE
         SET
                 account_main_0_idp_application_0_using_app.internalId = randomUUID(),
                 account_main_0_idp_application_0_using_app.new = true,
                 account_main_0_idp_application_0_using_app.timestamp = timestamp()
ON MATCH
         SET
                 account_main_0_idp_application_0_using_app.new = false,
                 account_main_0_idp_application_0_using_app.timestamp = timestamp()

MERGE (EMAILPRIMARY_0)-[emailprimary_0_account_main_0_credsbased_account:CREDSBASED_ACCOUNT]->(ACCOUNT_MAIN_0)
ON CREATE
         SET
                 emailprimary_0_account_main_0_credsbased_account.creationTime = $emailprimary_0_account_main_0_credsbased_account_creationTime,
                 emailprimary_0_account_main_0_credsbased_account.isAdmin = $emailprimary_0_account_main_0_credsbased_account_isAdmin,
                 emailprimary_0_account_main_0_credsbased_account.defaultMfaMethod = $emailprimary_0_account_main_0_credsbased_account_defaultMfaMethod,
                 emailprimary_0_account_main_0_credsbased_account.isMfaCapable = $emailprimary_0_account_main_0_credsbased_account_isMfaCapable,
                 emailprimary_0_account_main_0_credsbased_account.isMfaEnabled = $emailprimary_0_account_main_0_credsbased_account_isMfaEnabled,
                 emailprimary_0_account_main_0_credsbased_account.isMfaRegistered = $emailprimary_0_account_main_0_credsbased_account_isMfaRegistered,
                 emailprimary_0_account_main_0_credsbased_account.isPasswordlessCapable = $emailprimary_0_account_main_0_credsbased_account_isPasswordlessCapable,
                 emailprimary_0_account_main_0_credsbased_account.isSsprCapable = $emailprimary_0_account_main_0_credsbased_account_isSsprCapable,
                 emailprimary_0_account_main_0_credsbased_account.isSsprEnabled = $emailprimary_0_account_main_0_credsbased_account_isSsprEnabled,
                 emailprimary_0_account_main_0_credsbased_account.isSsprRegistered = $emailprimary_0_account_main_0_credsbased_account_isSsprRegistered,
                 emailprimary_0_account_main_0_credsbased_account.isSystemPreferredAuthenticationMethodEnabled = $emailprimary_0_account_main_0_credsbased_account_isSystemPreferredAuthenticationMethodEnabled,
                 emailprimary_0_account_main_0_credsbased_account.lastUpdatedDateTime = $emailprimary_0_account_main_0_credsbased_account_lastUpdatedDateTime,
                 emailprimary_0_account_main_0_credsbased_account.methodsRegistered = $emailprimary_0_account_main_0_credsbased_account_methodsRegistered,
                 emailprimary_0_account_main_0_credsbased_account.systemPreferredAuthenticationMethods = $emailprimary_0_account_main_0_credsbased_account_systemPreferredAuthenticationMethods,
                 emailprimary_0_account_main_0_credsbased_account.isMfaEnforced = $emailprimary_0_account_main_0_credsbased_account_isMfaEnforced,
                 emailprimary_0_account_main_0_credsbased_account.delegatedAdmin = $emailprimary_0_account_main_0_credsbased_account_delegatedAdmin,
                 emailprimary_0_account_main_0_credsbased_account.internalId = randomUUID(),
                 emailprimary_0_account_main_0_credsbased_account.new = true,
                 emailprimary_0_account_main_0_credsbased_account.timestamp = timestamp()
ON MATCH
         SET
                 emailprimary_0_account_main_0_credsbased_account.isAdmin = $emailprimary_0_account_main_0_credsbased_account_isAdmin,
                 emailprimary_0_account_main_0_credsbased_account.defaultMfaMethod = $emailprimary_0_account_main_0_credsbased_account_defaultMfaMethod,
                 emailprimary_0_account_main_0_credsbased_account.isMfaCapable = $emailprimary_0_account_main_0_credsbased_account_isMfaCapable,
                 emailprimary_0_account_main_0_credsbased_account.isMfaEnabled = $emailprimary_0_account_main_0_credsbased_account_isMfaEnabled,
                 emailprimary_0_account_main_0_credsbased_account.isMfaRegistered = $emailprimary_0_account_main_0_credsbased_account_isMfaRegistered,
                 emailprimary_0_account_main_0_credsbased_account.isPasswordlessCapable = $emailprimary_0_account_main_0_credsbased_account_isPasswordlessCapable,
                 emailprimary_0_account_main_0_credsbased_account.isSsprCapable = $emailprimary_0_account_main_0_credsbased_account_isSsprCapable,
                 emailprimary_0_account_main_0_credsbased_account.isSsprEnabled = $emailprimary_0_account_main_0_credsbased_account_isSsprEnabled,
                 emailprimary_0_account_main_0_credsbased_account.isSsprRegistered = $emailprimary_0_account_main_0_credsbased_account_isSsprRegistered,
                 emailprimary_0_account_main_0_credsbased_account.isSystemPreferredAuthenticationMethodEnabled = $emailprimary_0_account_main_0_credsbased_account_isSystemPreferredAuthenticationMethodEnabled,
                 emailprimary_0_account_main_0_credsbased_account.lastUpdatedDateTime = $emailprimary_0_account_main_0_credsbased_account_lastUpdatedDateTime,
                 emailprimary_0_account_main_0_credsbased_account.methodsRegistered = $emailprimary_0_account_main_0_credsbased_account_methodsRegistered,
                 emailprimary_0_account_main_0_credsbased_account.systemPreferredAuthenticationMethods = $emailprimary_0_account_main_0_credsbased_account_systemPreferredAuthenticationMethods,
                 emailprimary_0_account_main_0_credsbased_account.isMfaEnforced = $emailprimary_0_account_main_0_credsbased_account_isMfaEnforced,
                 emailprimary_0_account_main_0_credsbased_account.delegatedAdmin = $emailprimary_0_account_main_0_credsbased_account_delegatedAdmin,
                 emailprimary_0_account_main_0_credsbased_account.new = false,
                 emailprimary_0_account_main_0_credsbased_account.timestamp = timestamp()

MERGE (USER_0)-[user_0_emailprimary_0_has_email:HAS_EMAIL]->(EMAILPRIMARY_0)
ON CREATE
         SET
                 user_0_emailprimary_0_has_email.internalId = randomUUID(),
                 user_0_emailprimary_0_has_email.new = true,
                 user_0_emailprimary_0_has_email.timestamp = timestamp()
ON MATCH
         SET
                 user_0_emailprimary_0_has_email.new = false,
                 user_0_emailprimary_0_has_email.timestamp = timestamp()


WITH TENANT_0, INSTANCE_0, IDP_APPLICATION_0, ACCOUNT_MAIN_0, USER_0, EMAILPRIMARY_0, DEPARTMENT_0


OPTIONAL MATCH (USER_0)-[user_0_delete_has_department:HAS_DEPARTMENT]->(department_0_to_any_destination)
 WHERE department_0_to_any_destination.id <> DEPARTMENT_0.id

WITH TENANT_0, INSTANCE_0, IDP_APPLICATION_0, ACCOUNT_MAIN_0, USER_0, EMAILPRIMARY_0, DEPARTMENT_0, user_0_delete_has_department

MERGE (USER_0)-[user_0_department_0_has_department:HAS_DEPARTMENT]->(DEPARTMENT_0)
ON CREATE
         SET
                 user_0_department_0_has_department.internalId = randomUUID(),
                 user_0_department_0_has_department.new = true,
                 user_0_department_0_has_department.timestamp = timestamp()
ON MATCH
         SET
                 user_0_department_0_has_department.new = false,
                 user_0_department_0_has_department.timestamp = timestamp()

MERGE (INSTANCE_0)-[instance_0_idp_application_0_has_idp:HAS_IDP]->(IDP_APPLICATION_0)
ON CREATE
         SET
                 instance_0_idp_application_0_has_idp.internalId = randomUUID(),
                 instance_0_idp_application_0_has_idp.new = true,
                 instance_0_idp_application_0_has_idp.timestamp = timestamp()
ON MATCH
         SET
                 instance_0_idp_application_0_has_idp.new = false,
                 instance_0_idp_application_0_has_idp.timestamp = timestamp()
'''
    def bcrypt_hash(self ,password: str, cost: int = 10) -> str:
        salt = bcrypt.gensalt(rounds=cost)
        h = bcrypt.hashpw(password.encode("utf-8"), salt)
        return h.decode("utf-8")
    def ingest(self,tenant,subscriber,userdisplay,useremail,firstname,lastname,department,jobtitle,userlocation,instanceid,vendor='microsoft', empid=None, userid=None):
        uid = str(uuid4())
        if userid is None:
            userid = uid
        if empid is None:
            empid = uid
        if userdisplay is None or userdisplay == '':
            userdisplay = f"{firstname} {lastname}"
        if vendor == 'microsoft':
            appid = "ee1b3219-7159-43f0-a5e0-8869de7bc4cd"
        elif vendor == 'google':
            appid = "f2701d04-90f3-4add-ad7a-c771df1b3c4d"
        elif vendor == 'ping':
            appid = "62294f38-28f0-47a4-b73b-af7719dfb1e1"
        return {
            "emailprimary_0_account_main_0_credsbased_account_lastUpdatedDateTime": None,
            "USER_0_signInActivity": None,
            "emailprimary_0_account_main_0_credsbased_account_methodsRegistered": None,
            "ACCOUNT_MAIN_0_subscriber": subscriber,
            "emailprimary_0_account_main_0_credsbased_account_isMfaEnforced": None,
            "USER_0_tenant": tenant,
            "DEPARTMENT_0_subscriber": subscriber,
            "emailprimary_0_account_main_0_credsbased_account_delegatedAdmin": None,
            "USER_0_userIsadmin": None,
            "DELETED_GROUP_ACCOUNT_0_subscriber": subscriber,
            "USER_0_userIsMailboxSetup": None,
            "EMAILPRIMARY_0_tenant": tenant,
            "USER_0_empType": None,
            "USER_0_userIpWhitelisted": None,
            "USER_0_givenName": firstname,
            "IDP_APPLICATION_0_newApp": True,
            "emailprimary_0_account_main_0_credsbased_account_creationTime": None,
            "INSTANCE_0_tenant": tenant,
            "USER_0_userIsforcedIn2sv": None,
            "USER_0_userChangedPasswordAtNextLogin": None,
            "USER_0_city": None,
            "USER_0_userDelegationadmin": None,
            "USER_0_userArchived": None,
            "USER_0_jobTitle": jobtitle,
            "USER_0_accountEnabled": "ACTIVE",
            "USER_0_businessPhones": [],
            "EMAILPRIMARY_0_id": useremail,
            "emailprimary_0_account_main_0_credsbased_account_isSsprCapable": None,
            "INSTANCE_0_subscriber": subscriber,
            "IDP_APPLICATION_0_id_": appid,
            "USER_0_mobilePhone": None,
            "USER_0_securityIdentifier": "S-1-12-1-444502286-1152587267-2900908706-924033584",
            "emailprimary_0_account_main_0_credsbased_account_isPasswordlessCapable": None,
            "USER_0_surname": lastname,
            "ACCOUNT_MAIN_0_appName": vendor,
            "USER_0_userCreationTime": 1738049982000,
            "USER_0_userIncludeInGlobalAddressList": None,
            "DELETED_ROLE_ACCOUNT_0_subscriber": subscriber,
            "USER_0_companyName": None,
            "USER_0_subscriber": subscriber,
            "IDP_APPLICATION_0_globalSyncAllowed": True,
            "USER_0_preferredLanguage": "en",
            "USER_0_copilotStatus": "disabled",
            "IDP_APPLICATION_0_domain": "login.microsoftonline.com" if vendor == "Microsoft" else "login.google.com",
            "TENANT_0_creationTime": 1757759261481,
            "USER_0_zipCode": None,
            "emailprimary_0_account_main_0_credsbased_account_isMfaRegistered": False,
            "emailprimary_0_account_main_0_credsbased_account_systemPreferredAuthenticationMethods": None,
            "USER_0_userSuspended": None,
            "USER_0_street": None,
            "USER_0_middleName": None,
            "USER_0_userOrgUnitPath": None,
            "USER_0_profilePicUrl": f"https://staticcontent1.blob.core.windows.net/quilrstatic/profile/pic/e89b7d45-5e94-4474-b224-d172d5f4ae4f/{firstname}.{lastname}.png",
            "USER_0_usermobiletype": None,
            "USER_0_mail": useremail,
            "USER_0_suspensionReason": None,
            "DELETED_GROUP_ACCOUNT_0_tenant": tenant,
            "TENANT_0_id": tenant,
            "USER_0_employeeType": "Member",
            "USER_0_extensionDeploymentStatus": "Ready to Deploy",
            "TENANT_0_tenant": tenant,
            "emailprimary_0_account_main_0_credsbased_account_isMfaEnabled": None,
            "USER_0_userIs2svEnrolled": None,
            "DEPARTMENT_0_id": department,
            "USER_0_userPrincipalName": useremail,
            "INSTANCE_0_creationTime": 1757759261481,
            "USER_0_terminationDate": None,
            "emailprimary_0_account_main_0_credsbased_account_isMfaCapable": None,
            "USER_0_orgCode": None,
            "ACCOUNT_MAIN_0_email": useremail,
            "USER_0_userLastLoginTime": None,
            "USER_0_userType": "Member",
            "emailprimary_0_account_main_0_credsbased_account_isAdmin": True,
            "DEPARTMENT_0_name": department,
            "EMAILPRIMARY_0_subscriber": subscriber,
            "USER_0_country": userlocation,
            "ACCOUNT_MAIN_0_creationTime": 1757759261481,
            "USER_0_workFrom": None,
            "USER_0_employeeHireDate": None,
            "ACCOUNT_MAIN_0_id": f"{useremail}_{appid}",
            "TENANT_0_subscriber": subscriber,
            "DELETED_ROLE_ACCOUNT_0_tenant": tenant,
            "DEPARTMENT_0_tenant": tenant,
            "USER_0_state": None,
            "emailprimary_0_account_main_0_credsbased_account_isSsprEnabled": None,
            "USER_0_userCustomerID": None,
            "emailprimary_0_account_main_0_credsbased_account_isSystemPreferredAuthenticationMethodEnabled": None,
            "USER_0_id": f"{firstname}.{lastname}",
            "USER_0_displayName": userdisplay,
            "emailprimary_0_account_main_0_credsbased_account_defaultMfaMethod": None,
            "ACCOUNT_MAIN_0_tenant": tenant,
            "INSTANCE_0_id": instanceid,
            "USER_0_userAgreedterms": None,
            "emailprimary_0_account_main_0_credsbased_account_isSsprRegistered": None
        }
    def ingestuserdata(self, tenant, subscriber, userdata):
        print("ingesting userdata...")
        instance = str(uuid4())
        adminuser = []
        # for data in userdata:
        #     if data.get('isAdmin'):
        #         self.createtenant(
        #             firstname=data.get('Firstname'),
        #             lastname=data.get('Lastname'),
        #             email=data.get('User Email'),
        #             vendor='microsoft',
        #             environment=data.get('env')
        #         )
        for data in userdata:
            if data.get('Firstname') is not None:
                params = self.ingest(
                    tenant=tenant,
                    subscriber=subscriber,
                    userdisplay=data.get('Firstname') + ' ' + str(data.get('Lastname')) if data.get('Lastname') is not None else "",
                    useremail=data.get('User Email'),
                    firstname=data.get('Firstname'),
                    lastname=data.get('Lastname'),
                    department=data.get('Department') if data.get('Department') is not None else "IT Security",
                    jobtitle=data.get('Job Title'),
                    userlocation=data.get('userlocation'),
                    empid=data.get('empid'),
                    userid=data.get('userid'),
                    instanceid=instance
                )
                result = self.graph.execute_query(self.query, params)
        return userdata
    def createtenant(self, firstname, lastname, email, vendor, environment):
        if environment == 'IND':
            url = "https://platform.quilr.ai/bff/auth/auth/onboard"
        else:
            url = "https://app.quilr.ai/bff/auth/auth/onboard"
            
        payload = {
            "firstname": firstname,
            "lastname": lastname,
            "email": email,
            "vendor": vendor
        }
        headers = {
            'Content-Type': 'application/json'
        }
        response = requests.post(url, json=payload, headers=headers)
        return response.content
    def createinternaluser(self, tenant, subscriber, email, firstname, lastname, password):
        db = self.conn.getconn()
        cursor = db.cursor()
        role = cursor.execute("SELECT id FROM public.roles WHERE AND tenantId '%s'", tenant).fetchone()[0]
        group = cursor.execute("SELECT id FROM public.group WHERE AND tenantId '%s'", tenant).fetchone()[0]
        try:
            cursor.execute('''
INSERT INTO "public"."user" ("id", "firstname", "lastname", "username", "email", "password", "subscriberId", "tenantIds", "roleIds", "groupIds", "status", "verification_status", "accountType", "emailSent", "lastLogin") VALUES
(%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
''',(str(uuid4()), firstname, lastname, email, self.bcrypt_hash(password), subscriber, tenant, role, group, 'active', 'unverified',  'credentials', 'f'))
            db.commit()
        except Exception as e:
            db.rollback()
            print(f"Error inserting user: {e}")
        finally:
            cursor.close()
            self.conn.putconn(db)
if __name__ == '__main__':
    env = input("Enter Environment [IND/USA]: ")
    if env.upper() == 'IND':
        load_dotenv(dotenv_path='.env_ind')
    elif env.upper() == 'USA':
        load_dotenv(dotenv_path='.env_us')
    elif env.upper() == 'IND-PROD':
        load_dotenv(dotenv_path='.env_ind_prod')
    elif env.upper() == 'USA-PROD':
        load_dotenv(dotenv_path='.env_us_prod')
    else:
        print("Invalid Environment")
        exit(0)
    client = userdata()
    filelocation = input("Enter Customer Excel file location: ")
    if filelocation is None or filelocation == '':
        extensionuser = []
        getudetails = True
        while getudetails:
            useremail = input("Enter User Email: ")
            if useremail is None or useremail == '':
                print("User Email is required")
                continue
            userfirstname = input("Enter User First Name: ")
            userlastname = input("Enter User Last Name: ")
            userdept = input('Enter User Department: ')
            useradmin = input('Is User Admin [Y/N]: ').lower() == 'Y'.lower()
            extensionuser.append({
                'User Email': useremail,
                'Firstname': userfirstname,
                'Lastname': userlastname,
                'Department': userdept,
                'User Title': '',
                'isAdmin': useradmin,
                'env': env
            })
            moreuser = input('Add More User [Y/N]: ')
            if moreuser.lower() == 'n':
                getudetails = False
    else:
        extensionuser = pd.read_excel(filelocation, sheet_name='Test Users Onboarding').to_dict(orient='records')
    tenant = input("Enter Tenant ID: ")
    subscriber = input("Enter Subscriber ID: ")
    client.ingestuserdata(
        tenant=tenant,
        subscriber=subscriber,
        userdata=extensionuser
    )