/* eslint-disable jsx-a11y/anchor-is-valid */

import * as ReactDOM from "react-dom";
import * as React from "react";
import { ResponsiveBar } from "@nivo/bar";
import { range, uniq } from "lodash";
import ErrorBoundary from "../ErrorBoundary";
import GlobalAppContext, { GlobalAppContextT } from "../GlobalAppContext";
import BrainzPlayer from "../BrainzPlayer";
import Pill from "../components/Pill";
import {
  WithAlertNotificationsInjectedProps,
  withAlertNotifications,
} from "../AlertNotificationsHOC";

import APIServiceClass from "../APIService";
import { getPageProps } from "../utils";
import ComponentToImage from "./ComponentToImage";

import fakeData from "./year-in-music-data.json";
import ListenCard from "../listens/ListenCard";
import UserListModalEntry from "../follow/UserListModalEntry";

export type YearInMusicProps = {
  user: ListenBrainzUser;
} & WithAlertNotificationsInjectedProps;

export type YearInMusicState = {
  loading: boolean;
  selectedRelease?: ColorReleaseItem;
  selectedTopEntity: Entity;
};

export default class YearInMusic extends React.Component<
  YearInMusicProps,
  YearInMusicState
> {
  static contextType = GlobalAppContext;
  declare context: React.ContextType<typeof GlobalAppContext>;

  constructor(props: YearInMusicProps) {
    super(props);
    this.state = {
      loading: false,
      selectedTopEntity: "recording",
    };
  }

  selectTopEntity = (entity: Entity) => {
    this.setState({ selectedTopEntity: entity });
  };

  render() {
    const { user, newAlert } = this.props;
    const { loading, selectedRelease, selectedTopEntity } = this.state;
    const { APIService, currentUser } = this.context;
    const selectedReleaseTracks = selectedRelease?.recordings ?? [];
    const totalListens = 12345;
    const mostActiveDay = "Friday";

    /* Most listened years */
    const mostListenedYears = Object.keys(fakeData.most_listened_year);
    // Ensure there are no holes between years
    const filledYears = range(
      Number(mostListenedYears[0]),
      Number(mostListenedYears[mostListenedYears.length - 1])
    );
    const mostListenedYearDataForGraph = filledYears.map((year: number) => ({
      year,
      // Add a 0 for years without data
      albums:
        fakeData.most_listened_year[
          String(year) as keyof typeof fakeData.most_listened_year
        ] ?? 0,
    }));

    return (
      <div role="main" id="year-in-music">
        <div className="row center-block">
          <div className="col-sm-6 center-p">
            <img
              className="img-responsive header-image"
              src="/static/img/year-in-music-2021.svg"
              alt="Your year in music 2021"
            />
            <div>
              <h4>
                <div>Share your year with your friends</div>
                <p>
                  <a
                    href={`https://listenbrainz.org/user/${user?.name}/year-in-music`}
                  >
                    https://listenbrainz.org/user/{user?.name}/year-in-music
                  </a>
                </p>
              </h4>
            </div>
          </div>
          <div className="col-sm-6">
            <h1>{user?.name}</h1>
            <div style={{ marginTop: "20px", marginBottom: "20px" }}>
              <img
                src="../../../../static/img/musicbrainz-16.svg"
                alt="MusicBrainz Logo"
              />
              <b>
                <a href={`https://musicbrainz.org/user/${user.name}`}>
                  See profile on MusicBrainz
                </a>
              </b>
            </div>
            <div className="row">
              <div className="col-sm-6">
                <div className="card flex-center">
                  <h3 className="text-center">
                    You listened to 12345 songs this year
                  </h3>
                </div>
              </div>
              <div className="col-sm-6">
                <div className="card flex-center">
                  <h3 className="text-center">
                    Your most active listening day
                  </h3>
                  <div>Friday</div>
                </div>
              </div>
              {/* <div className="col-sm-4">
              <div className="card flex-center">
                <h3 className="text-center">
                  Average color of your top albums:
                  <div
                    style={{
                      width: "100%",
                      height: "65px",
                      background: `rgb${fakeData.most_prominent_color}`,
                    }}
                  />
                </h3>
              </div>
            </div> */}
            </div>
          </div>
        </div>
        <hr className="wide" />
        <div className="row">
          <div className="col-sm-12">
            <div className="card">
              <h3>
                Your top {selectedTopEntity}s of the year
                <Pill
                  active={selectedTopEntity === "recording"}
                  // eslint-disable-next-line react/jsx-no-bind
                  onClick={this.selectTopEntity.bind(this, "recording")}
                >
                  Tracks
                </Pill>{" "}
                <Pill
                  active={selectedTopEntity === "release"}
                  // eslint-disable-next-line react/jsx-no-bind
                  onClick={this.selectTopEntity.bind(this, "release")}
                >
                  Albums
                </Pill>{" "}
                <Pill
                  active={selectedTopEntity === "artist"}
                  // eslint-disable-next-line react/jsx-no-bind
                  onClick={this.selectTopEntity.bind(this, "artist")}
                >
                  Artists
                </Pill>{" "}
              </h3>
              <ComponentToImage />
            </div>
          </div>
        </div>
        <div className="row">
          <div className="col-md-7">
            <div className="card" id="top-discoveries">
              <h3 className="text-center">
                Your top discoveries published in 2021
              </h3>
              <div className="scrollable-area">
                Extract info from a JSPF playlist, show first 5 items, link to
                full playlist
              </div>
            </div>
          </div>
          <div className="col-md-5">
            <div className="card" id="most-listened-year">
              <h3 className="text-center">
                What year are your favorite albums from?
                <div className="small">
                  How much were you on the lookout for new music this year? Not
                  that we&apos;re judging.
                </div>
              </h3>
              <div className="graph">
                <ResponsiveBar
                  margin={{ left: 30, bottom: 30 }}
                  data={mostListenedYearDataForGraph}
                  padding={0.1}
                  layout="vertical"
                  keys={["albums"]}
                  indexBy="year"
                  colors="#eb743b"
                  enableLabel={false}
                  axisBottom={{
                    // Round to nearest 5 year mark
                    tickValues: uniq(
                      mostListenedYearDataForGraph.map(
                        (datum) => Math.round((datum.year + 1) / 5) * 5
                      )
                    ),
                  }}
                />
              </div>
            </div>
          </div>
        </div>
        <div className="row">
          <div className="col-md-5">
            <div className="card" id="similar-users">
              <h3 className="text-center">
                Music buddies
                <div className="small">
                  Here are the users with the most similar taste to you this
                  year. Maybe go check them out?
                </div>
              </h3>
              <div className="scrollable-area similar-users-list">
                {fakeData.similar_users &&
                  Object.keys(fakeData.similar_users).map(
                    (userName: string, index) => {
                      return (
                        <UserListModalEntry
                          mode="similar-users"
                          key={userName}
                          user={{
                            name: userName,
                            similarityScore:
                              fakeData.similar_users[
                                userName as keyof typeof fakeData.similar_users
                              ],
                          }}
                          loggedInUserFollowsUser={false}
                          updateFollowingList={() => {}}
                        />
                      );
                    }
                  )}
              </div>
            </div>
          </div>
          <div className="col-md-7">
            <div className="card" id="new-releases">
              <h3 className="text-center">
                New albums of your top artists
                <div className="small">
                  New albums released in 2021 from your favorite artists.
                </div>
              </h3>
              <div className="scrollable-area">
                {fakeData.new_releases_of_top_artists.map((release) => (
                  <ListenCard
                    key={release.release_id}
                    compact
                    listen={{
                      listened_at: 0,
                      listened_at_iso: release.first_release_date,
                      track_metadata: {
                        artist_name: release.artist_credit_names.join(", "),
                        track_name: release.title,
                        release_name: release.title,
                        additional_info: {
                          release_mbid: release.release_id,
                          artist_mbids: release.artist_credit_mbids,
                        },
                      },
                    }}
                    showTimestamp
                    showUsername={false}
                    newAlert={newAlert}
                  />
                ))}
              </div>
            </div>
          </div>
        </div>
        <div className="row">
          <div className="col-sm-12">
            <div className="card">
              <h3 className="text-center">
                We made some personnalized playlists for you !
              </h3>
              <div className="row">
                <div className="col-md-4">Playlist #1</div>
                <div className="col-md-4">Playlist #2</div>
                <div className="col-md-4">Playlist #3</div>
              </div>
            </div>
          </div>
        </div>
        <hr className="wide" />
        <BrainzPlayer
          listens={[]}
          newAlert={newAlert}
          listenBrainzAPIBaseURI={APIService.APIBaseURI}
          refreshSpotifyToken={APIService.refreshSpotifyToken}
          refreshYoutubeToken={APIService.refreshYoutubeToken}
        />
      </div>
    );
  }
}

document.addEventListener("DOMContentLoaded", () => {
  const { domContainer, reactProps, globalReactProps } = getPageProps();
  const { api_url, current_user, spotify, youtube } = globalReactProps;
  const { user } = reactProps;

  const apiService = new APIServiceClass(
    api_url || `${window.location.origin}/1`
  );

  const YearInMusicWithAlertNotifications = withAlertNotifications(YearInMusic);

  const globalProps: GlobalAppContextT = {
    APIService: apiService,
    currentUser: current_user,
    spotifyAuth: spotify,
    youtubeAuth: youtube,
  };

  ReactDOM.render(
    <ErrorBoundary>
      <GlobalAppContext.Provider value={globalProps}>
        <YearInMusicWithAlertNotifications user={user} />
      </GlobalAppContext.Provider>
    </ErrorBoundary>,
    domContainer
  );
});
