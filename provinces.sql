-- phpMyAdmin SQL Dump
-- version 5.1.1
-- https://www.phpmyadmin.net/
--
-- Host: localhost
-- Generation Time: Oct 28, 2021 at 07:53 AM
-- Server version: 10.4.19-MariaDB
-- PHP Version: 7.4.20

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Database: `inva_db`
--

-- --------------------------------------------------------

--
-- Table structure for table `provinces`
--

CREATE TABLE `provinces` (
  `id` int(11) NOT NULL,
  `name` varchar(120) CHARACTER SET utf8 NOT NULL,
  `name_en` varchar(120) CHARACTER SET utf8 DEFAULT NULL,
  `active` tinyint(4) NOT NULL DEFAULT 1,
  `is_city` tinyint(4) NOT NULL DEFAULT 0,
  `created_at` timestamp NOT NULL DEFAULT current_timestamp(),
  `updated_at` timestamp NOT NULL DEFAULT current_timestamp() ON UPDATE current_timestamp()
) ENGINE=InnoDB DEFAULT CHARSET=utf8 COLLATE=utf8_unicode_ci;

--
-- Dumping data for table `provinces`
--

INSERT INTO `provinces` (`id`, `name`, `name_en`, `active`, `is_city`, `created_at`, `updated_at`) VALUES
(1, 'បន្ទាយមានជ័យ', 'Banteay Meanchey', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(2, 'បាត់ដំបង', 'Battambang', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(3, 'កំពង់ចាម', 'Kampong Cham', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(4, 'កំពង់ឆ្នាំង', 'Kampong Chhnang', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(5, 'កំពង់ស្ពឺ', 'Kampong Speu', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(6, 'កំពង់ធំ', 'Kampong Thom', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(7, 'កំពត', 'Kampot', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(8, 'កណ្តាល', 'Kandal', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(9, 'កោះកុង', 'Koh Kong', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(10, 'ក្រចេះ', 'Kratie', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(11, 'មណ្ឌលគិរី', 'Mondul Kiri', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(12, 'ភ្នំពេញ', 'Phnom Penh', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(13, 'ព្រះវិហារ', 'Preah Vihear', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(14, 'ព្រៃវែង', 'Prey Veng', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(15, 'ពោធិ៍សាត់', 'Pursat', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(16, 'រតនគិរី', 'Ratanak Kiri', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(17, 'សៀមរាប', 'Siem Reap', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(18, 'ព្រះសីហនុ', 'Preah Sihanouk', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(19, 'ស្ទឹងត្រែង', 'Stung Treng', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(20, 'ស្វាយរៀង', 'Svay Rieng', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(21, 'តាកែវ', 'Takeo', 1, 0, '2020-12-17 03:51:59', '2021-08-16 06:50:30'),
(22, 'ឧត្តរមានជ័យ', 'Oddar Meanchey', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(23, 'កែប', 'Kep', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(24, 'ប៉ៃលិន', 'Pailin', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59'),
(25, 'ត្បូងឃ្មុំ', 'Tboung Khmum', 1, 0, '2020-12-17 03:51:59', '2020-12-17 03:51:59');

--
-- Indexes for dumped tables
--

--
-- Indexes for table `provinces`
--
ALTER TABLE `provinces`
  ADD PRIMARY KEY (`id`);

--
-- AUTO_INCREMENT for dumped tables
--

--
-- AUTO_INCREMENT for table `provinces`
--
ALTER TABLE `provinces`
  MODIFY `id` int(11) NOT NULL AUTO_INCREMENT, AUTO_INCREMENT=26;
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
