import {
  AppAuthError,
  AuthorizationServiceConfiguration,
  BasicQueryStringUtils,
  FetchRequestor,
  Requestor,
  type QueryStringUtils,
  type StringMap,
} from "@openid/appauth";

export interface UserInfoRequestJson {
  access_token: string;
}

export interface UserInfoResponseJson {
  sub: string;
  nickname: string;
  preferred_username: string;
  email: string;
  name: string;
}

export interface UserInfoErrorJson {
  error: "invalid_request" | "unsupported_response_type";
  error_description?: string;
  error_uri?: string;
}

export class UserInfoRequest {
  accessToken: string;

  constructor(request: UserInfoRequestJson) {
    this.accessToken = request.access_token;
  }

  toJson(): UserInfoRequestJson {
    return {
      access_token: this.accessToken,
    };
  }

  toStringMap(): StringMap {
    return {
      access_token: this.accessToken,
    };
  }
}

export class UserInfoRequestHandler {
  constructor(
    public readonly requestor: Requestor = new FetchRequestor(),
    public readonly utils: QueryStringUtils = new BasicQueryStringUtils()
  ) {}

  private isValid(
    response: UserInfoResponseJson | UserInfoErrorJson
  ): response is UserInfoResponseJson {
    return (response as UserInfoErrorJson).error === undefined;
  }

  performUserInfoRequest(
    configuration: AuthorizationServiceConfiguration,
    request: UserInfoRequest
  ): Promise<UserInfoResponseJson> {
    const response = this.requestor.xhr<
      UserInfoResponseJson | UserInfoErrorJson
    >({
      url: configuration.userInfoEndpoint,
      method: "POST",
      dataType: "json", // adding implicit dataType
      headers: { "Content-Type": "application/x-www-form-urlencoded" },
      data: this.utils.stringify(request.toStringMap()),
    });

    return response.then((response) => {
      if (this.isValid(response)) {
        return response;
      } else {
        return Promise.reject<UserInfoResponseJson>(
          new AppAuthError(response.error, response)
        );
      }
    });
  }
}
