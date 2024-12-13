create database hosting;

use hosting;

drop table if exists Subscribers;
drop table if exists SearchHistory;
drop table if exists Ratings;
drop table if exists RatingTypes;
drop table if exists Comments;
drop table if exists ViewHistory;
drop table if exists UserRoles;
drop table if exists AccessLevels;
drop table if exists Users;
drop table if exists MediaTagsConnector;
drop table if exists Tags;
drop table if exists Media;
drop table if exists Companies;
create table Users (
  IdUser int not null primary key auto_increment,
  Email varchar(255) not null unique,
  LoginUser varchar(255) not null unique,
  NameUser varchar(255),
  Surname varchar(255),
  Patronymic varchar(255),
  Birthday datetime,
  RegisterTime timestamp,
  About varchar(255),
  Password varchar(255) not null,
  IsAdmin boolean default 0
);

create table Companies(
  IdCompany int not null primary key auto_increment,
  Name varchar(255) not null,
  About text(65535)
);

create table Subscribers (
  IdSubscriber int not null primary key auto_increment,
  IdCompany int,
  foreign key (IdCompany) references Companies(IdCompany),
  IdUser int,
  foreign key(IdUser) references Users(IdUser)
);

create table SearchHistory(
  IdSearchHistory int not null primary key auto_increment,
  IdUser int,
  foreign key(IdUser) references Users(IdUser),
  SearchQuery varchar(255),
  SearchTime timestamp
);

create table Media(
  IdMedia int not null primary key auto_increment,
  IdCompany int,
  foreign key(IdCompany) references Companies(IdCompany),
  NameV varchar(255) not null,
  DescriptionV varchar(10000),
  UploadTime timestamp,
  VideoPath varchar(255) not null unique
);

create table RatingTypes(
  IdRatingType int not null primary key auto_increment,
  NameRating varchar(20) not null,
  RatingFactor int not null
);

create table Ratings(
  IdRating int not null primary key auto_increment,
  IdUser int,
  foreign key(IdUser) references Users(IdUser),
  IdMedia int,
  foreign key(IdMedia) references Media(IdMedia),
  IdRatingType int,
  foreign key(IdRatingType) references RatingTypes(IdRatingType),
  RatingTime timestamp
);

create table Comments(
  IdComment int not null primary key auto_increment,
  IdUser int,
  foreign key(IdUser) references Users(IdUser),
  IdMedia int,
  foreign key(IdMedia) references Media(IdMedia),
  TextComment varchar(10000) not null,
  Date datetime not null
);

create table ViewHistory(
  IdViewHistory int not null primary key auto_increment,
  IdUser int,
  foreign key(IdUser) references Users(IdUser),
  IdMedia int,
  foreign key(IdMedia) references Media(IdMedia),
  ViewTime timestamp
);

create table AccessLevels(
  IdAccessLevel int not null primary key auto_increment,
  AccessName varchar(20) not null,
  AccessLevel int not null default 1
);

create table UserRoles(
  IdUser int,
  foreign key(IdUser) references Users(IdUser),
  IdCompany int,
  foreign key(IdCompany) references Companies(IdCompany),
  IdAccessLevel int,
  foreign key(IdAccessLevel) references AccessLevels(IdAccessLevel)
);

create table Tags(
  IdTag int not null primary key auto_increment,
  TagName varchar(50) not null
);

create table MediaTagsConnector(
  IdConnection int not null primary key auto_increment,
  IdTag int,
  FOREIGN KEY(IdTag) REFERENCES Tags(IdTag),
  IdMedia int,
  FOREIGN KEY(IdMedia) REFERENCES Media(IdMedia)
);
