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
drop table if exists Reports;
drop table if exists Users;
drop table if exists MediaTagsConnector;
drop table if exists Tags;
drop table if exists Media;
drop table if exists MediaPreview;
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
  Password varchar(255) not null
);

create table CompanyLogo(
  IdCompanyLogo int not null auto_increment primary key,
  LogoPath varchar(1024) not null
);

insert into CompanyLogo(LogoPath) value ("logo/default_logo.jpg");

create table Companies(
  IdCompany int not null primary key auto_increment,
  Name varchar(255) not null,
  About text(65535),
  IdCompanyLogo int not null default 1,
  foreign key(IdCompanyLogo) references CompanyLogo(IdCompanyLogo)
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

create table Reports(
  IdReport int not null primary key auto_increment,
  ReportTime datetime not null,
  IdComment int not null,
  IdUser int not null,
  ReportReason varchar(10000),
  FOREIGN KEY(IdComment) REFERENCES Comments(IdComment),
  FOREIGN KEY(IdUser) REFERENCES Users(IdUser)
);

create table RatingTypes(
  IdRatingType int not null primary key auto_increment,
  NameRating varchar(20) not null,
  RatingFactor int not null
);

LOCK TABLES `RatingTypes` WRITE;
/*!40000 ALTER TABLE `RatingTypes` DISABLE KEYS */;
INSERT INTO `RatingTypes` VALUES (1,'None',0),(2,'Like',1),(3,'Dislike',-1);
/*!40000 ALTER TABLE `RatingTypes` ENABLE KEYS */;
UNLOCK TABLES;

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
  ViewTime timestamp,
  ViewCount int not null default 1
);

create table AccessLevels(
  IdAccessLevel int not null primary key auto_increment,
  AccessName varchar(20) not null,
  AccessLevel int not null default 1
);

LOCK TABLES `AccessLevels` WRITE;
/*!40000 ALTER TABLE `AccessLevels` DISABLE KEYS */;
INSERT INTO `AccessLevels` VALUES (4,'Admin',10),(2,'Moderator',3),(3,'Company Owner',5),(1,'User',1);
/*!40000 ALTER TABLE `AccessLevels` ENABLE KEYS */;
UNLOCK TABLES;

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

LOCK TABLES `Tags` WRITE;
/*!40000 ALTER TABLE `Tags` DISABLE KEYS */;
INSERT INTO `Tags` VALUES (1,'Корпорація'),(3,'Компанія'),(5,'Менеджмент'),(6,'Лідерство'),(7,'Інновації'),(8,'Стратегія'),(9,'Економіка'),(10,'Фінанси'),(11,'Маркетинг'),(12,'Підприємництво'),(13,'HR'),(14,'Технології'),(15,'Команда'),(16,'Співробітники'),(17,'Корпоративна Зустріч'),(18,'Тренінг'),(19,'Мотивація'),(20,'Новинки'),(21,'Продукти'),(22,'Послуги'),(23,'Технологічний Прогрес'),(24,'Соціальна Відповідальність'),(25,'Успіх'),(26,'Довіра'),(27,'Надійність'),(28,'Україна'),(29,'Міжнародний Бізнес'),(30,'ІТ'),(31,'Фармацевтика'),(32,'Агробізнес');
/*!40000 ALTER TABLE `Tags` ENABLE KEYS */;
UNLOCK TABLES;


create table MediaTagsConnector(
  IdConnection int not null primary key auto_increment,
  IdTag int,
  FOREIGN KEY(IdTag) REFERENCES Tags(IdTag),
  IdMedia int,
  FOREIGN KEY(IdMedia) REFERENCES Media(IdMedia)
);

create table MediaPreview(
  IdMediaPreview int not null auto_increment primary key,
  PreviewPath varchar(1024) not null
);

insert into MediaPreview(PreviewPath) values ("previews/default_video.jpg"), ("default_audio.jpg");
