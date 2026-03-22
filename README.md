[![](https://img.shields.io/badge/kilter_together_1.0.0-passing-green)](https://github.com/gongahkia/kilter-together/releases/tag/1.0.0)
![](https://github.com/gongahkia/kilter-together/actions/workflows/ci.yml/badge.svg)

# `Kilter Together`

[Collaborative](#features) [P2P](#other-nerd-stuff) [Sessioning app](#architecture) for the climbing community.

***Currently supports [Kilter & Crux boards](#supported-boards)!!!***

## Stack

* *Frontend, Backend*: [Dart](), [Riverpod]()
* *Framework*: [Flutter]()
* *DB*: [SQLite]()
* *P2P Transport Layer*: [Swift](), [Google Nearby Connections]()
* *Board Data*: []()
* *Package*: []()
* *CI/CD*: [GitHub Actions]()

## Usage

The below instructions are for building `Kilter Together` from source.

1. First run the below to install `Kilter Together` on your local machine.

```console
$ git clone https://github.com/gongahkia/kilter-together && cd kilter-together-mobile
```

2. Then run the below to build `Kilter Together` on [your device](#supported-platforms).

```
$ flutter pub get
$ flutter run
```

3. See [here](#other-nerd-stuff) for more nerd details.

## Features

* Create and host collaborative climbing sessions *(Kilter Board, Crux-supported boards)*
* Join sessions via QR scan, deep link, or nearby discovery
* Vote on climbs with real-time sync
* Manage climb queue and finalists
* Solo catalog browsing with grade filtering
* Session recap with local history
* Offline-first Kilter dataset
* Plan sharing between sessions

## Screenshots

<div align="center">
  <img src="./asset/reference/1.png" width="32%">
  <img src="./asset/reference/2.png" width="32%">
  <img src="./asset/reference/3.png" width="32%">
</div>

<div align="center">
  <img src="./asset/reference/4.png" width="32%">
  <img src="./asset/reference/5.png" width="32%">
  <img src="./asset/reference/6.png" width="32%">
</div>

## Architecture

![](./asset/reference/architecture.png)

## Supported platforms

... Add table about which mobile platforms/web it can support currently

## Supported boards

... Add table about which boards are supported

## Other nerd stuff

... Add details about every stage of the app